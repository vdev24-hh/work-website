import uuid

from flask import request

import db
import hashing


def get(s=None):
    
    r = None if s is None else request.db.query(db.Session).filter_by(cookie=hashing.hash_session(s)).first()
    
    if r is None:
        
        s = str(uuid.uuid4())
        r = db.Session(cookie=hashing.hash_session(s))
        request.db.add(r)
        request.db.commit()
        
        r.plain_cookie = s
        return r
    
    r.plain_cookie = None
    return r


def set(**kwargs):
    for k, v in kwargs.items():
        setattr(request.session, k, v)
    request.db.commit()


def message(text):
    set(message=text)