import cv2
import numpy as np
import logging
from pymongo import MongoClient
from config import Config
import datetime
import xml.etree.ElementTree as ET

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB setup
client = MongoClient(Config.MONGO_URI)
db = client['online_exam']
proctoring_logs = db['proctoring_logs']

# TensorFlow model setup
model = None
try:
    import tensorflow as tf
    logger.info(f"TensorFlow version: {tf.__version__}")
    model = tf.keras.Sequential([
        tf.keras.layers.Conv2D(32, (3, 3), activation='relu', input_shape=(64, 64, 1)),
        tf.keras.layers.MaxPooling2D((2, 2)),
        tf.keras.layers.Flatten(),
        tf.keras.layers.Dense(64, activation='relu'),
        tf.keras.layers.Dense(1, activation='sigmoid')
    ])
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    logger.info("Malpractice detection model initialized successfully")
except ImportError as e:
    logger.error(f"Failed to import TensorFlow/Keras: {str(e)}")
except Exception as e:
    logger.error(f"Failed to initialize model: {str(e)}")

def generate_proctoring_xml(student_id, exam_id, result, log_entries):
    root = ET.Element("ProctoringReport")
    
    ET.SubElement(root, "StudentID").text = str(student_id)
    ET.SubElement(root, "ExamID").text = str(exam_id)
    ET.SubElement(root, "MalpracticeDetected").text = "Yes" if result else "No"

    logs_elem = ET.SubElement(root, "Logs")
    for entry in log_entries:
        event_elem = ET.SubElement(logs_elem, "Event")
        ET.SubElement(event_elem, "Timestamp").text = entry["timestamp"].isoformat()
        ET.SubElement(event_elem, "Message").text = entry["event"]

    tree = ET.ElementTree(root)
    filename = f"proctoring_report_{student_id}_{exam_id}.xml"
    tree.write(filename, encoding='utf-8', xml_declaration=True)
    logger.info(f"XML report saved as {filename}")
    return filename

def start_proctoring(student_id, exam_id):
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            logger.error("Failed to open webcam")
            return None

        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(f'proctoring_{student_id}_{exam_id}.avi', fourcc, 20.0, (640, 480))

        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        if face_cascade.empty():
            logger.error("Failed to load face cascade classifier")
            cap.release()
            return None

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)
            if len(faces) == 0:
                log = {
                    'student_id': student_id,
                    'exam_id': exam_id,
                    'event': 'No face detected',
                    'timestamp': datetime.datetime.now()
                }
                proctoring_logs.insert_one(log)
            out.write(frame)

        cap.release()
        out.release()
        logger.info(f"Proctoring video saved for student {student_id}, exam {exam_id}")
        return f'proctoring_{student_id}_{exam_id}.avi'
    except Exception as e:
        logger.error(f"Proctoring failed: {str(e)}")
        return None

def detect_malpractice(file_path, student_id, exam_id):
    if not model:
        logger.warning("Malpractice detection model not available, skipping detection")
        return False

    try:
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            logger.error(f"Failed to open video file {file_path}")
            return False

        malpractice_detected = False
        logs = []

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            resized = cv2.resize(gray, (64, 64))
            input_data = resized.reshape(1, 64, 64, 1) / 255.0

            prediction = model.predict(input_data, verbose=0)
            if prediction[0][0] > 0.5:  # Threshold
                log_entry = {
                    'student_id': student_id,
                    'exam_id': exam_id,
                    'event': 'Suspicious activity detected',
                    'timestamp': datetime.datetime.now()
                }
                proctoring_logs.insert_one(log_entry)
                logs.append(log_entry)
                malpractice_detected = True

        cap.release()
        logger.info(f"Malpractice detection completed for {file_path}")

        # Generate XML report
        generate_proctoring_xml(student_id, exam_id, malpractice_detected, logs)

        return malpractice_detected
    except Exception as e:
        logger.error(f"Malpractice detection failed: {str(e)}")
        return False
