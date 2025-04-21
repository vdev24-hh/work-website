from datetime import datetime, timedelta
from decimal import Decimal
from functools import wraps

from flask import Flask, make_response, render_template, redirect, url_for, request
from sqlalchemy import or_

import db
import hashing
import sessions


def fg(k):
    return request.form.get(k)


def rct(*args, **kwargs):
    return redirect(url_for(*args, **kwargs))


def login_required(function):
    @wraps(function)
    def f(*args, **kwargs):
        if request.session.user is None:
            return rct('login_get')
        return function(*args, **kwargs)
    return f


app = Flask(__name__)


@app.context_processor
def context_processor():
    return dict(len=len, enumerate=enumerate)


@app.before_request
def before_request():
    
    if request.endpoint=='static':
        return
    
    request.db = db.SessionLocal()
    
    request.session = sessions.get(request.cookies.get('s'))
    
    if request.session.message:
        request.message = request.session.message
        request.session.message = None
        request.db.commit()
    else:
        request.message = None
    
    
@app.after_request
def after_request(resp):
    
    if request.endpoint=='static':
        return resp
    
    if request.session.plain_cookie:
        resp = make_response(resp)
        resp.set_cookie('s', request.session.plain_cookie, expires=datetime.now()+timedelta(days=30))
    
    request.db.close()
    
    return resp


@app.get('/')
def tasks_get():
    
    q = request.args.get('q')
    
    tasks = request.db.query(db.Task)
    if q:
        tasks = tasks.filter(db.Task.name.ilike(f'%{q}%'))
    tasks = tasks.order_by(db.Task.id.desc()).all()
    
    return render_template('tasks.html', tasks=tasks)


@app.get('/my-tasks')
def my_tasks_get():
    return render_template(
        'user_tasks.html',
        tasks=request.db.query(db.Task).filter(or_(
            db.Task.user_id==request.session.user_id,
            db.Task.employee_id==request.session.user_id
        )).order_by(db.Task.id.desc()).all()
    )


@app.get('/logout')
def logout_get():
    request.db.delete(request.session)
    request.db.commit()
    return rct('tasks_get')


@app.get('/login')
def login_get():
    return render_template('auth.html')


@app.post('/login')
def login_post():
    
    username = fg('username')
    user = request.db.query(db.User).filter_by(username=username).first()
    
    if not (user is not None and hashing.verify_password(user.password, fg('password'))):
        sessions.message('Invalid username or password')
        return rct('login_get')
    
    sessions.set(user_id=user.id)
    return rct('tasks_get')


@app.get('/register')
def register_get():
    return render_template('auth.html', register=True)


@app.post('/register')
def register_post():
    
    username, password = fg('username'), fg('password')
    
    if not (username and password):
        sessions.message('Enter username and password')
        return rct('register_get')
    
    if request.db.query(db.User).filter_by(username=username).first() is not None:
        sessions.message('User already exists')
        return rct('register_get')
    
    user = db.User(username=username, password=hashing.hash_password(password))
    request.db.add(user)
    request.db.commit()
    sessions.set(user_id=user.id)
    
    return rct('tasks_get')


@app.get('/task/<int:task_id>')
def task_get(task_id):
    task = request.db.query(db.Task).filter_by(id=task_id).first()
    return render_template('task.html', task=task)


@app.post('/task/<int:task_id>')
def task_post(task_id):
    
    r = rct('task_get', task_id=task_id)
    task = request.db.query(db.Task).filter_by(id=task_id).first()
    
    done, cancel = fg('done'), fg('cancel')
    if (done or cancel) and not task.status:
        if task.employee_id != request.session.user_id:
            sessions.message("You're not the employee")
            return r
        task.status = 1 if done else 2
        request.db.commit()
        return r
    
    review_text = fg('review')
    if review_text and task.status:
        if request.session.user_id not in (task.user_id, task.employee_id):
            sessions.message('You cannot write a review')
            return r
        if request.session.user_id in (review.user_id for review in task.reviews):
            sessions.message('You have already left a review')
            return r
        request.db.add(db.Review(task_id=task_id, user_id=request.session.user_id, text=review_text))
        request.db.commit()
        return r
    
    if task.user_id==request.session.user_id:
        if task.employee is not None:
            sessions.message('Already selected employee')
            return r
        employee_username = fg('employee_username')
        employee = request.db.query(db.User).filter_by(username=employee_username).first()
        if employee is None:
            sessions.message('Employee not found')
            return r
        task.employee_id = employee.id
        request.db.commit()
        return r
    if request.session.user_id in task.get_proposals_by_user_id():
        sessions.message('Already sent')
        return r
    text = fg('proposal')
    if not text:
        sessions.message('Enter text')
        return r
    request.db.add(db.Proposal(task_id=task_id,
                               user_id=request.session.user_id,
                               text=text))
    request.db.commit()
    return r


@app.get('/task')
@login_required
def new_task_get():
    return render_template('new_task.html')


@app.post('/task')
@login_required
def new_task_post():
    
    task_name = fg('name')
    task_price = fg('price')
    task_description = fg('description')

    new_task = db.Task(
        user_id=request.session.user_id,
        name=task_name,
        price=task_price,
        description=task_description,
    )

    request.db.add(new_task)
    request.db.commit()

    return rct('tasks_get')


def get_user_reviews(user_id):
    
    reviews = {'By employers': [], 'By employees': []}
    
    tasks = request.db.query(db.Task).filter(
        or_(
            db.Task.user_id==user_id,
            db.Task.employee_id==user_id
        )
    ).all()
    
    for task in tasks:
        for review in task.reviews:
            if review.user_id != user_id:
                reviews['By employers' if review.user_id==task.user_id else 'By employees'].append(review)
    
    return {k: sorted(v, key=lambda review: review.id, reverse=True) for k, v in reviews.items()}


@app.get('/profile')
@login_required
def profile_get():
    return render_template('profile.html',
                           user_reviews=get_user_reviews(request.session.user_id))


@app.get('/profile/edit')
@login_required
def edit_profile_get():
    return render_template('profile.html', edit=True)


@app.post('/profile/edit')
@login_required
def edit_profile_post():
    request.session.user.description = fg('description')
    request.db.commit()
    return rct('profile_get')


@app.get('/users/<username>')
def user_get(username):
    if username==request.session.user.username:
        return rct('profile_get')
    user = request.db.query(db.User).filter_by(username=username).first()
    if user is None:
        return rct('tasks_get')
    return render_template('profile.html',
                           user=user,
                           user_reviews=get_user_reviews(user.id))


@app.get('/balance')
@login_required
def balance_get():
    return render_template('balance.html')


@app.post('/balance')
@login_required
def balance_post():
    price = fg('price')
    try:
        float(price)
    except:
        sessions.message('Invalid amount')
        return rct('balance_get')
    request.session.user.balance = request.session.user.get_balance() + Decimal(price)
    request.db.commit()
    sessions.message('Balance replenished')
    return rct('balance_get')


if __name__ == '__main__':
    app.run()