# models.py
from datetime import datetime, date
from flask_login import UserMixin
from extensions import db

class Watchlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    symbol = db.Column(db.String(20), nullable=False)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    name = db.Column(db.String(100))
    avatar = db.Column(db.String(50), default='fa-user')
    special_role = db.Column(db.String(50), default="REGULAR")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    plan_type = db.Column(db.String(20), default='Starter')
    alerts = db.relationship('PriceAlert', backref='owner', lazy=True)
    watchlist = db.relationship('Watchlist', backref='owner', lazy=True)
    virtual_balance = db.Column(db.Float, default=10000.0)
    portfolio = db.relationship('Portfolio', backref='owner', lazy=True)
    transactions = db.relationship('Transaction', backref='owner', lazy=True)
    ai_usage_count = db.Column(db.Integer, default=0) 
    last_ai_usage = db.Column(db.Date, nullable=True) 

class Portfolio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    symbol = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    avg_price = db.Column(db.Float, nullable=False)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    symbol = db.Column(db.String(20), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    price = db.Column(db.Float, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    total_value = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class PriceAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    symbol = db.Column(db.String(20), nullable=False)
    target_price = db.Column(db.Float, nullable=False)
    condition = db.Column(db.String(10), nullable=False) # 'above' (acima de) ou 'below' (abaixo de)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)