from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
import csv
from io import StringIO
import random
import json
import logging
from config import Config


exam_bp = Blueprint('exam', __name__)
client = MongoClient(Config.MONGO_URI)
db = client['online_exam']
exams_collection = db['exams']
submissions_collection = db['submissions']
users_collection = db['users']

# Configure logging
logger = logging.getLogger(__name__)

@exam_bp.route('/create-exam', methods=['POST', 'OPTIONS'])
@jwt_required(optional=True)  # Allow OPTIONS without JWT
def create_exam():
    logger.info(f"Received {request.method} request to create exam")

    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:4200')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Max-Age', '86400')  # Cache preflight for 24 hours
        logger.info("Responded to OPTIONS preflight request")
        return response, 200

    # For POST, ensure JWT is present
    current_user = get_jwt_identity()
    if not current_user:
        logger.error("No JWT identity found for POST request")
        return jsonify({'message': 'Missing authorization token'}), 401

    logger.info(f"Current user: {current_user}")
    if current_user.get('role') not in ['teacher', 'examiner']:
        logger.warning(f"Unauthorized role: {current_user.get('role')} for user {current_user.get('email')}")
        return jsonify({'message': 'Unauthorized'}), 403

    data = request.form.to_dict()
    questions = []

    # Debug: Log received form data
    logger.info(f"Received form data: {dict(request.form)}")
    if 'csv_file' in request.files:
        logger.info("CSV file detected")
    if request.form.getlist('questions[]'):
        logger.info(f"Manual questions received: {request.form.getlist('questions[]')}")

    # Process CSV file if provided
    if 'csv_file' in request.files:
        csv_file = request.files['csv_file']
        if csv_file.filename.endswith('.csv'):
            stream = StringIO(csv_file.stream.read().decode('UTF-8'))
            csv_reader = csv.DictReader(stream)
            for row in csv_reader:
                if row['type'].lower() == 'mcq':
                    questions.append({
                        'question': row['question'],
                        'options': [row['option1'], row['option2'], row['option3'], row['option4']],
                        'correct_option': int(row['correct_option']),
                        'difficulty': row['difficulty'],
                        'type': 'mcq'
                    })
                else:
                    questions.append({
                        'question': row['question'],
                        'difficulty': row['difficulty'],
                        'type': 'subjective'
                    })
            logger.info(f"Processed {len(questions)} questions from CSV")

    # If no CSV, process manual questions
    elif request.form.getlist('questions[]'):
        question_data = request.form.getlist('questions[]')
        for q in question_data:
            try:
                q_dict = json.loads(q)  # Use json.loads for safe parsing
                if q_dict['type'] == 'mcq':
                    questions.append({
                        'question': q_dict['question'],
                        'options': q_dict['options'],
                        'correct_option': q_dict['correct_option'],
                        'difficulty': q_dict['difficulty'],
                        'type': 'mcq'
                    })
                else:
                    questions.append({
                        'question': q_dict['question'],
                        'difficulty': q_dict['difficulty'],
                        'type': 'subjective'
                    })
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse question: {q}, Error: {str(e)}")
                return jsonify({'message': 'Invalid question format in manual questions'}), 400
        logger.info(f"Processed {len(questions)} manual questions")

    if not questions:
        logger.error("No questions provided after processing")
        return jsonify({'message': 'No questions provided. Please provide questions via CSV or manually.'}), 400

    exam = {
        'title': data['title'],
        'duration': int(data['duration']),
        'questions': questions,
        'scheduled_for': datetime.strptime(data['scheduled_for'], '%Y-%m-%dT%H:%M:%S.%fZ'),
        'randomized': data.get('randomized') == 'true',
        'difficulty': data['difficulty'],
        'created_at': datetime.utcnow(),
        'created_by': current_user['email'],
        'status': 'scheduled'
    }
    if exam['randomized']:
        random.shuffle(exam['questions'])
    result = exams_collection.insert_one(exam)
    logger.info(f"Exam created with ID: {str(result.inserted_id)}")
    return jsonify({'message': 'Exam created successfully', 'exam_id': str(result.inserted_id)}), 201

@exam_bp.route('/edit-exam/<exam_id>', methods=['PATCH', 'OPTIONS'])
@jwt_required(optional=True)
def edit_exam(exam_id):
    logger.info(f"Received {request.method} request to edit exam {exam_id}")
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:4200')
        response.headers.add('Access-Control-Allow-Methods', 'PATCH, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Max-Age', '86400')
        logger.info("Responded to OPTIONS preflight request")
        return response, 200

    current_user = get_jwt_identity()
    if not current_user:
        logger.error("No JWT identity found for PATCH request")
        return jsonify({'message': 'Missing authorization token'}), 401

    if current_user.get('role') not in ['teacher', 'examiner']:
        return jsonify({'message': 'Unauthorized'}), 403

    exam = exams_collection.find_one({'_id': ObjectId(exam_id), 'created_by': current_user['email']})
    if not exam:
        return jsonify({'message': 'Exam not found or unauthorized'}), 404

    data = request.form.to_dict()
    update = {}
    if 'title' in data:
        update['title'] = data['title']
    if 'duration' in data:
        update['duration'] = int(data['duration'])
    if 'scheduled_for' in data:
        update['scheduled_for'] = datetime.strptime(data['scheduled_for'], '%Y-%m-%dT%H:%M')
    if 'randomized' in data:
        update['randomized'] = data['randomized'] == 'true'
    if 'difficulty' in data:
        update['difficulty'] = data['difficulty']

    questions = []
    if 'csv_file' in request.files:
        csv_file = request.files['csv_file']
        if csv_file.filename.endswith('.csv'):
            stream = StringIO(csv_file.stream.read().decode('UTF-8'))
            csv_reader = csv.DictReader(stream)
            for row in csv_reader:
                if row['type'].lower() == 'mcq':
                    questions.append({
                        'question': row['question'],
                        'options': [row['option1'], row['option2'], row['option3'], row['option4']],
                        'correct_option': int(row['correct_option']),
                        'difficulty': row['difficulty'],
                        'type': 'mcq'
                    })
                else:
                    questions.append({
                        'question': row['question'],
                        'difficulty': row['difficulty'],
                        'type': 'subjective'
                    })
    elif request.form.getlist('questions[]'):
        for q in request.form.getlist('questions[]'):
            q_dict = json.loads(q)
            if q_dict['type'] == 'mcq':
                questions.append({
                    'question': q_dict['question'],
                    'options': q_dict['options'],
                    'correct_option': q_dict['correct_option'],
                    'difficulty': q_dict['difficulty'],
                    'type': 'mcq'
                })
            else:
                questions.append({
                    'question': q_dict['question'],
                    'difficulty': q_dict['difficulty'],
                    'type': 'subjective'
                })
    if questions:
        update['questions'] = questions
        if update.get('randomized', exam['randomized']):
            random.shuffle(update['questions'])

    if update:
        exams_collection.update_one({'_id': ObjectId(exam_id)}, {'$set': update})
        return jsonify({'message': 'Exam updated successfully'})
    return jsonify({'message': 'No changes provided'}), 400

@exam_bp.route('/delete-exam/<exam_id>', methods=['DELETE', 'OPTIONS'])
@jwt_required(optional=True)
def delete_exam(exam_id):
    logger.info(f"Received {request.method} request to delete exam {exam_id}")
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:4200')
        response.headers.add('Access-Control-Allow-Methods', 'DELETE, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Max-Age', '86400')
        return response, 200

    current_user = get_jwt_identity()
    if not current_user:
        return jsonify({'message': 'Missing authorization token'}), 401

    if current_user.get('role') not in ['teacher', 'examiner']:
        return jsonify({'message': 'Unauthorized'}), 403

    result = exams_collection.delete_one({'_id': ObjectId(exam_id), 'created_by': current_user['email']})
    if result.deleted_count == 0:
        return jsonify({'message': 'Exam not found or unauthorized'}), 404
    return jsonify({'message': 'Exam deleted successfully'})

@exam_bp.route('/get-exams', methods=['GET', 'OPTIONS'])
@jwt_required(optional=True)
def get_exams():
    logger.info(f"Received {request.method} request to get exams")
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:4200')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Max-Age', '86400')
        logger.info("Responded to OPTIONS preflight request")
        return response, 200

    current_user = get_jwt_identity()
    if not current_user:
        return jsonify({'message': 'Missing authorization token'}), 401

    now = datetime.utcnow()
    query = {'status': 'scheduled'}
    if current_user.get('role') in ['teacher', 'examiner']:
        query['created_by'] = current_user['email']
    else:
        query['scheduled_for'] = {'$lte': now}

    exams = exams_collection.find(query).sort('scheduled_for', 1)
    result = []
    for exam in exams:
        submission = submissions_collection.find_one({
            'exam_id': str(exam['_id']),
            'user_email': current_user['email']
        }) if current_user.get('role') == 'student' else None
        exam_data = {
            'exam_id': str(exam['_id']),
            'title': exam['title'],
            'duration': exam['duration'],
            'scheduled_for': exam['scheduled_for'].isoformat(),
            'randomized': exam['randomized'],
            'difficulty': exam['difficulty'],
            'questions': exam['questions'] if current_user.get('role') in ['teacher', 'examiner'] or exam['scheduled_for'] <= now else [],
            'status': exam['status']
        }
        if submission:
            exam_data['submission'] = {
                'status': submission['status'],
                'answers': submission['answers'],
                'mcq_score': submission['score'],
                'subjective_marks': submission.get('subjective_marks', 0),
                'total_marks': submission.get('total_marks', 0),
                'rank': submission.get('rank', ''),
                'start_time': submission.get('start_time', '').isoformat() if submission.get('start_time') else None
            }
        result.append(exam_data)
    return jsonify(result)

@exam_bp.route('/get-exams/<exam_id>', methods=['GET', 'OPTIONS'])
@jwt_required(optional=True)
def get_exam_by_id(exam_id):
    logger.info(f"Received {request.method} request to get exam {exam_id}")
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:4200')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Max-Age', '86400')
        logger.info("Responded to OPTIONS preflight request")
        return response, 200
    
    current_user = get_jwt_identity()
    if not current_user:
        return jsonify({'message': 'Missing authorization token'}), 401
    
    exam = exams_collection.find_one({'_id': ObjectId(exam_id)})
    if not exam:
        return jsonify({'message': 'Exam not found'}), 404
    
    exam_data = {
        'exam_id': str(exam['_id']),
        'title': exam['title'],
        'duration': exam['duration'],
        'scheduled_for': exam['scheduled_for'].isoformat(),
        'randomized': exam['randomized'],
        'difficulty': exam['difficulty'],
        'questions': exam['questions'] if current_user.get('role') in ['teacher', 'examiner'] else [],
        'status': exam['status']
    }
    return jsonify(exam_data), 200

@exam_bp.route('/submit-exam', methods=['POST', 'OPTIONS'])
@jwt_required(optional=True)
def submit_exam():
    logger.info(f"Received {request.method} request to submit exam")
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:4200')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Max-Age', '86400')
        return response, 200

    current_user = get_jwt_identity()
    if not current_user:
        return jsonify({'message': 'Missing authorization token'}), 401

    if current_user.get('role') != 'student':
        return jsonify({'message': 'Unauthorized'}), 403

    data = request.get_json()
    exam = exams_collection.find_one({'_id': ObjectId(data['exam_id'])})
    if not exam:
        return jsonify({'message': 'Exam not found'}), 404
    if exam['scheduled_for'] > datetime.utcnow():
        return jsonify({'message': 'Exam not yet available'}), 403

    submission = submissions_collection.find_one({
        'exam_id': data['exam_id'],
        'user_email': current_user['email']
    })
    if submission and submission['status'] == 'completed':
        return jsonify({'message': 'Exam already submitted'}), 400

    score = 0
    answers = data['answers']
    for i, q in enumerate(exam['questions']):
        if q['type'] == 'mcq' and answers[i] and answers[i].get('answer') is not None:
            if isinstance(answers[i].get('answer'), (int, str)) and int(answers[i].get('answer')) == q['correct_option']:
                score += 1

    if submission:
        submissions_collection.update_one(
            {'_id': submission['_id']},
            {'$set': {
                'answers': answers,
                'score': score,
                'submitted_at': datetime.utcnow(),
                'status': 'completed'
            }}
        )
    else:
        submissions_collection.insert_one({
            'exam_id': data['exam_id'],
            'user_email': current_user['email'],
            'student_id': current_user['student_id'],
            'answers': answers,
            'score': score,
            'start_time': data.get('start_time', datetime.utcnow()),
            'submitted_at': datetime.utcnow(),
            'status': 'completed'
        })
    return jsonify({'message': 'Exam submitted successfully'})

@exam_bp.route('/start-exam/<exam_id>', methods=['POST', 'OPTIONS'])
@jwt_required(optional=True)
def start_exam(exam_id):
    logger.info(f"Received {request.method} request to start exam {exam_id}")
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:4200')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        return response, 200

    current_user = get_jwt_identity()
    if not current_user:
        return jsonify({'message': 'Missing authorization token'}), 401
    if current_user.get('role') != 'student':
        return jsonify({'message': 'Unauthorized'}), 403

    exam = exams_collection.find_one({'_id': ObjectId(exam_id)})
    if not exam:
        return jsonify({'message': 'Exam not found'}), 404

    # Check if exam is scheduled and available
    now = datetime.utcnow()
    if exam['scheduled_for'] > now:
        return jsonify({'message': 'Exam not yet available'}), 400

    # Check if submission already exists
    submission = submissions_collection.find_one({
        'exam_id': exam_id,
        'user_email': current_user['email']
    })
    if submission:
        return jsonify({
            'message': 'Exam already started',
            'start_time': submission['start_time'].isoformat(),
            'duration': exam['duration']  # Return duration in minutes
        }), 200

    # Create new submission
    submission = {
        'exam_id': exam_id,
        'user_email': current_user['email'],
        'start_time': now,
        'status': 'in_progress',
        'answers': [],
        'score': 0
    }
    submissions_collection.insert_one(submission)
    return jsonify({
        'message': 'Exam started successfully',
        'start_time': now.isoformat(),
        'duration': exam['duration']  # Return duration in minutes
    }), 200

@exam_bp.route('/evaluate-exam', methods=['POST', 'OPTIONS'])
@jwt_required(optional=True)
def evaluate_exam():
    logger.info(f"Received {request.method} request to evaluate exam")
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:4200')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Max-Age', '86400')
        return response, 200

    current_user = get_jwt_identity()
    if not current_user:
        return jsonify({'message': 'Missing authorization token'}), 401

    if current_user.get('role') not in ['teacher', 'examiner']:
        return jsonify({'message': 'Unauthorized'}), 403

    data = request.get_json()
    submission = submissions_collection.find_one({
        'exam_id': data['exam_id'],
        'user_email': data['user_email']
    })
    if not submission:
        return jsonify({'message': 'Submission not found'}), 404

    subjective_marks = sum(float(m) for m in data['subjective_marks'] if m is not None)
    total_marks = submission['score'] + subjective_marks
    rank = data['rank']

    submissions_collection.update_one(
        {'_id': submission['_id']},
        {'$set': {
            'subjective_marks': subjective_marks,
            'total_marks': total_marks,
            'rank': rank,
            'status': 'completed'
        }}
    )
    return jsonify({'message': 'Exam evaluated successfully'})

@exam_bp.route('/get-submission/<exam_id>/<user_email>', methods=['GET', 'OPTIONS'])
@jwt_required(optional=True)
def get_submission(exam_id, user_email):
    logger.info(f"Received {request.method} request to get submission for exam {exam_id}, user {user_email}")
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:4200')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Max-Age', '86400')
        return response, 200

    current_user = get_jwt_identity()
    if not current_user:
        return jsonify({'message': 'Missing authorization token'}), 401

    if current_user.get('role') not in ['teacher', 'examiner']:
        return jsonify({'message': 'Unauthorized'}), 403

    submission = submissions_collection.find_one({
        'exam_id': exam_id,
        'user_email': user_email
    })
    if not submission:
        return jsonify({'message': 'Submission not found'}), 404

    exam = exams_collection.find_one({'_id': ObjectId(exam_id)})
    if not exam:
        return jsonify({'message': 'Exam not found'}), 404

    return jsonify({
        'exam_id': exam_id,
        'user_email': user_email,
        'title': exam['title'],
        'questions': exam['questions'],
        'answers': submission['answers'],
        'mcq_score': submission['score'],
        'subjective_marks': submission.get('subjective_marks', 0),
        'total_marks': submission.get('total_marks', 0),
        'rank': submission.get('rank', ''),
        'status': submission['status'],
        'start_time': submission.get('start_time', '').isoformat() if submission.get('start_time') else None
    })

@exam_bp.route('/get-student/<student_email>', methods=['GET', 'OPTIONS'])
@jwt_required(optional=True)
def get_student(student_email):
    logger.info(f"Received {request.method} request to get student {student_email}")
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:4200')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Max-Age', '86400')
        return response, 200

    current_user = get_jwt_identity()
    if not current_user:
        return jsonify({'message': 'Missing authorization token'}), 401

    if current_user.get('role') not in ['teacher', 'examiner']:
        return jsonify({'message': 'Unauthorized'}), 403

    student = users_collection.find_one({'email': student_email, 'role': 'student'})
    if not student:
        return jsonify({'message': 'Student not found'}), 404

    return jsonify({
        'name': student['name'],
        'email': student['email'],
        'student_id': student['student_id']
    })