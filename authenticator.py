from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
import secrets
import re
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta  # <-- fixed import
from functools import wraps
import jwt

load_dotenv()

app = Flask(__name__)
SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.secret_key = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///userinfo.db'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)

    def __init__(self, username, email, password):
        self.username = username
        self.email = email
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')

    @staticmethod
    def validate_password(password):
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'
        if not re.match(pattern, password):
            return False, "Password must contain at least one uppercase letter, one lowercase letter, one number, and one special character (@$!%*?&)"
        return True, "Password is valid"

    @staticmethod
    def validate_email(email):
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            return False, "Invalid email format"
        return True, "Email is valid"

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers.get('Authorization')
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            current_user = User.query.filter_by(id=data['user_id']).first()
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except Exception:
            return jsonify({'message': 'Token is invalid'}), 401

        return f(current_user, *args, **kwargs)
    return decorated

@app.route('/')
def index():
    return jsonify({'message': 'Authentication API is running...'})

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    is_valid_email, email_message = User.validate_email(data['email'])
    if not is_valid_email:
        return jsonify({'message': email_message}), 400
    is_valid, message = User.validate_password(data['password'])
    if not is_valid:
        return jsonify({'message': message}), 400
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email address already exists'}), 400
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'message': 'Username already exists'}), 400
    user = User(data['username'], data['email'], data['password'])
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': 'Registration successful'})

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data['email']).first()
    if not user or not bcrypt.check_password_hash(user.password, data['password']):
        return jsonify({'message': 'Invalid credentials'}), 401

    # Generate JWT token
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.utcnow() + timedelta(hours=1)  # <-- fixed datetime usage
    }, SECRET_KEY, algorithm="HS256")

    return jsonify({
        'message': 'Login successful',
        'token': token
    })

@app.route('/profile', methods=['GET'])
@token_required
def profile(current_user):
    return jsonify({'message': f'Karibu sana, {current_user.username}!'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
