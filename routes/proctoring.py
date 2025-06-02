from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.ai_proctoring import start_proctoring, detect_malpractice
from services.drive_service import upload_video
from pymongo import MongoClient
from config import Config
import datetime
from flask_mail import Mail, Message
import logging

proctoring_bp = Blueprint('proctoring', __name__)
client = MongoClient(Config.MONGO_URI)
db = client['online_exam']
proctoring_logs = db['proctoring_logs']
submissions_collection = db['submissions']
users_collection = db['users']
mail = Mail()

logger = logging.getLogger(__name__)

@proctoring_bp.route('/start-proctoring', methods=['POST', 'OPTIONS'])
@jwt_required()
def start_proctoring_route():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:4200')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        return response, 200
    current_user = get_jwt_identity()
    if current_user.get('role') != 'proctor':
        return jsonify({'message': 'Unauthorized'}), 403

    data = request.get_json()
    student_id = data['student_id']
    exam_id = data['exam_id']
    submission = submissions_collection.find_one({'exam_id': exam_id, 'student_id': student_id})
    if not submission or submission['status'] != 'in_progress':
        return jsonify({'message': 'No active exam session found'}), 400

    file_path = start_proctoring(student_id, exam_id)
    if not file_path:
        return jsonify({'message': 'Failed to record proctoring session'}), 500

    try:
        file_id = upload_video(file_path, f'proctoring_{student_id}_{exam_id}.avi')
        malpractice_detected = detect_malpractice(file_path, student_id, exam_id)
        if malpractice_detected:
            proctor = users_collection.find_one({'role': 'proctor'})
            student = users_collection.find_one({'student_id': student_id})
            if proctor and student:
                msg = Message('Malpractice Alert', sender=Config.MAIL_USERNAME, recipients=[proctor['email'], student['email']])
                msg.body = f'Malpractice detected for student {student_id} in exam {exam_id}. Please review.'
                mail.send(msg)
                logger.info(f"Malpractice alert sent for student {student_id}")
        return jsonify({'message': 'Proctoring session recorded and uploaded', 'file_id': file_id})
    except Exception as e:
        logger.error(f"Proctoring failed: {str(e)}")
        return jsonify({'message': 'Proctoring failed'}), 500

@proctoring_bp.route('/log-malpractice', methods=['POST', 'OPTIONS'])
@jwt_required()
def log_malpractice():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:4200')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        return response, 200
    current_user = get_jwt_identity()
    if current_user.get('role') != 'proctor':
        return jsonify({'message': 'Unauthorized'}), 403

    data = request.get_json()
    log = {
        'student_id': data['student_id'],
        'exam_id': data['exam_id'],
        'event': data['event'],
        'timestamp': datetime.datetime.now()
    }
    proctoring_logs.insert_one(log)
    return jsonify({'message': 'Malpractice logged'})

@proctoring_bp.route('/stop-exam/<exam_id>/<student_id>', methods=['POST', 'OPTIONS'])
@jwt_required()
def stop_exam(exam_id, student_id):
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:4200')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        return response, 200
    current_user = get_jwt_identity()
    if current_user.get('role') != 'proctor':
        return jsonify({'message': 'Unauthorized'}), 谱

    submission = submissions_collection.find_one({'exam_id': exam_id, 'student_id': student_id})
    if not submission or submission['status'] != 'in_progress':
        return jsonify({'message': 'No active exam session found'}), 400

    submissions_collection.update_one(
        {'exam_id': exam_id, 'student_id': student_id},
        {'$set': {'status': 'terminated', 'terminated_at': datetime.datetime.now()}}
    )

    try:
        student = users_collection.find_one({'student_id': student_id})
        if student:
            msg = Message('Exam Terminated', sender=Config.MAIL_USERNAME, recipients=[student['email']])
            msg.body = f'Your exam {exam_id} has been terminated due to malpractice.'
            mail.send(msg)
            logger.info(f"Termination email sent to student {student_id}")
    except Exception as e:
        logger.error(f"Failed to send termination email: {str(e)}")

    return jsonify({'message': 'Exam terminated successfully'})

@proctoring_bp.route('/proctoring-logs', methods=['GET', 'OPTIONS'])
@jwt_required()
def get_proctoring_logs():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:4200')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        return response, 200

    current_user = get_jwt_identity()
    if current_user.get('role') != 'proctor':
        return jsonify({'message': 'Unauthorized'}), 403

    logs = proctoring_logs.find()
    result = [{
        'student_id': log['student_id'],
        'exam_id': log['exam_id'],
        'event': log['event'],
        'timestamp': log['timestamp'].isoformat()
    } for log in logs]
    return jsonify(result), 200

@proctoring_bp.route('/download-report/<student_id>/<exam_id>', methods=['GET'])
def download_report(student_id, exam_id):
    filename = f"proctoring_report_{student_id}_{exam_id}.xml"
    folder_path = os.path.dirname(os.path.abspath(__file__))  # Same folder as the script
    try:
        return send_from_directory(folder_path, filename, as_attachment=True)
    except FileNotFoundError:
        return {"error": "Report not found"}, 404