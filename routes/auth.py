from flask import Blueprint, request, jsonify, make_response
from pymongo import MongoClient
from flask_jwt_extended import create_access_token
from flask_mail import Mail, Message
import bcrypt
import random
from config import Config

auth_bp = Blueprint('auth', __name__)
client = MongoClient(Config.MONGO_URI)
db = client['online_exam']
users_collection = db['users']
mail = Mail()

@auth_bp.route('/register', methods=['POST', 'OPTIONS'])
def register():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://online-exam-system-nine.vercel.app')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response, 200
    data = request.get_json()
    password = data['password'].encode('utf-8')
    hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
    user = {
        'name': data['name'],
        'email': data['email'],
        'password': hashed_password,
        'role': data['role'],
        'student_id': data['email'] if data['role'] == 'student' else None
    }
    if users_collection.find_one({'email': data['email']}):
        return jsonify({'message': 'Email already exists'}), 400
    result = users_collection.insert_one(user)
    return jsonify({'message': 'User registered successfully'}), 201

@auth_bp.route('/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://online-exam-system-nine.vercel.app')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response, 200
    data = request.get_json()
    user = users_collection.find_one({'email': data['email']})
    if user and bcrypt.checkpw(data['password'].encode('utf-8'), user['password']):
        token = create_access_token(identity={'email': user['email'], 'role': user['role'], 'student_id': user.get('student_id')})
        return jsonify({
            'token': token,
            'user': {
                'email': user['email'],
                'role': user['role'],
                'name': user['name'],
                'student_id': user.get('student_id')
            }
        })
    return jsonify({'message': 'Invalid credentials'}), 401

@auth_bp.route('/forgot-password', methods=['POST', 'OPTIONS'])
def forgot_password():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://online-exam-system-nine.vercel.app')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response, 200
    data = request.get_json()
    user = users_collection.find_one({'email': data['email']})
    if user:
        verification_code = str(random.randint(100000, 999999))
        users_collection.update_one({'email': data['email']}, {'$set': {'reset_code': verification_code}})
        msg = Message('Password Reset Verification Code', sender=Config.MAIL_USERNAME, recipients=[data['email']])
        msg.body = f'Your verification code is: {verification_code}\nThis code is valid for 10 minutes.'
        mail.send(msg)
        return jsonify({'message': 'Verification code sent to your email'})
    return jsonify({'message': 'User not found'}), 404

@auth_bp.route('/verify-code', methods=['POST', 'OPTIONS'])
def verify_code():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://online-exam-system-nine.vercel.app')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response, 200
    data = request.get_json()
    user = users_collection.find_one({'email': data['email'], 'reset_code': data['code']})
    if user:
        return jsonify({'message': 'Code verified successfully'})
    return jsonify({'message': 'Invalid or expired code'}), 400

@auth_bp.route('/reset-password', methods=['POST', 'OPTIONS'])
def reset_password():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://online-exam-system-nine.vercel.app')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response, 200
    data = request.get_json()
    user = users_collection.find_one({'email': data['email'], 'reset_code': data['code']})
    if user:
        new_password = data['newPassword'].encode('utf-8')
        hashed_password = bcrypt.hashpw(new_password, bcrypt.gensalt())
        users_collection.update_one(
            {'email': data['email']},
            {'$set': {'password': hashed_password, 'reset_code': None}}
        )
        return jsonify({'message': 'Password reset successfully'})
    return jsonify({'message': 'Invalid or expired code'}), 400