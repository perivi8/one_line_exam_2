from flask import Blueprint, request, jsonify, make_response
from pymongo import MongoClient
from flask_jwt_extended import jwt_required, get_jwt_identity
from config import Config
import datetime

queries_bp = Blueprint('queries', __name__)
client = MongoClient(Config.MONGO_URI)
db = client['online_exam']
queries_collection = db['queries']

@queries_bp.route('/raise-query', methods=['POST', 'OPTIONS'])
@jwt_required()
def raise_query():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://online-exam-system-nine.vercel.app')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        return response, 200
    current_user = get_jwt_identity()
    if current_user.get('role') != 'student':
        return jsonify({'message': 'Unauthorized'}), 403

    data = request.get_json()
    query = {
        'exam_id': data['exam_id'],
        'student_id': data['student_id'],
        'query_text': data['query_text'],
        'submitted_at': datetime.datetime.fromisoformat(data['submitted_at']),
        'status': 'pending'
    }
    queries_collection.insert_one(query)
    return jsonify({'message': 'Query submitted successfully'}), 200 , 