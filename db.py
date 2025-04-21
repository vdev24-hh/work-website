from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, Column, Numeric, SmallInteger, BigInteger, DateTime, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship


Base = declarative_base()


class CustomBase(Base):
    __abstract__ = True
    id = Column(BigInteger, primary_key=True)
    created_at = Column(DateTime, default=lambda: datetime.now(tz=timezone.utc))


class Session(CustomBase):
    __tablename__ = 'sessions'
    cookie = Column(String, unique=True)
    user_id = Column(BigInteger, ForeignKey('users.id'))
    message = Column(String)
    user = relationship('User')


class User(CustomBase):
    __tablename__ = 'users'
    username = Column(String, unique=True)
    password = Column(String)
    description = Column(String)
    balance = Column(Numeric)
    
    def get_balance(self):
        return Decimal() if self.balance is None else self.balance
    
    def get_balance_text(self):
        return f'{self.get_balance():.2f}'


class Task(CustomBase):
    __tablename__ = 'tasks'
    name = Column(String)
    price = Column(Numeric)
    description = Column(String)
    user_id = Column(BigInteger, ForeignKey('users.id'))
    employee_id = Column(BigInteger, ForeignKey('users.id'))
    status = Column(SmallInteger)
    user = relationship('User', foreign_keys=[user_id])
    employee = relationship('User', foreign_keys=[employee_id])
    proposals = relationship('Proposal')
    reviews = relationship('Review')
    
    def get_price_text(self):
        return f'{self.price:.2f}'.rstrip('0').rstrip('.')
    
    def get_proposals_by_user_id(self):
        return {proposal.user_id: proposal for proposal in self.proposals}
    
    def get_proposals_sorted_by_id(self):
        return sorted(self.proposals, key=lambda proposal: proposal.id, reverse=True)

    def get_reviews(self):
        return sorted(self.reviews, key=lambda review: review.user_id==self.employee_id)
    
    def has_review(self, is_employee=False):
        return (self.employee_id if is_employee else self.user_id) in (review.user_id for review in self.reviews)


class Proposal(CustomBase):
    __tablename__ = 'proposals'
    task_id = Column(BigInteger, ForeignKey('tasks.id'))
    user_id = Column(BigInteger, ForeignKey('users.id'))
    text = Column(String)
    user = relationship('User')


class Review(CustomBase):
    __tablename__ = 'reviews'
    task_id = Column(BigInteger, ForeignKey('tasks.id'))
    user_id = Column(BigInteger, ForeignKey('users.id'))
    text = Column(String)
    user = relationship('User')


engine = create_engine('postgresql://workwebsite:workwebsite@localhost/workwebsite')
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(autoflush=False, bind=engine)