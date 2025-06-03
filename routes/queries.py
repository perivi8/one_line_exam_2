from flask import Blueprint, request, jsonify, make_response
from pymongo import MongoClient
from flask_jwt_extended import jwt_required, get_jwt_identity
from config import Config
from datetime import datetime
import logging

queries_bp = Blueprint('queries', __name__)
client = MongoClient(Config.MONGO_URI)
db = client['online_exam']
queries_collection = db['queries']

logger = logging.getLogger(__name__)

@queries_bp.route('/raise-query', methods=['POST', 'OPTIONS'])
@jwt_required()
def raise_query():
    logger.info(f"Received {request.method} request to raise query")
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://online-exam-system-nine.vercel.app')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Max-Age', '86400')
        logger.info("Responded to OPTIONS preflight request")
        return response, 200

    current_user = get_jwt_identity()
    if not current_user:
        return jsonify({'message': 'Missing authorization token'}), 401
    if current_user.get('role') != 'student':
        return jsonify({'message': 'Unauthorized'}), 403

    data = request.get_json()
    if not data or not all(key in data for key in ['exam_id', 'student_id', 'query_text', 'submitted_at']):
        return jsonify({'message': 'Missing required fields'}), 400

    try:
        submitted_at = datetime.fromisoformat(data['submitted_at'])
    except ValueError:
        return jsonify({'message': 'Invalid date format for submitted_at'}), 400

    query = {
        'exam_id': data['exam_id'],
        'student_id': data['student_id'],
        'query_text': data['query_text'],
        'submitted_at': submitted_at,
        'status': 'pending'
    }
    queries_collection.insert_one(query)
    logger.info(f"Query raised by student {data['student_id']} for exam {data['exam_id']}")
    return jsonify({'message': 'Query submitted successfully'}), 201