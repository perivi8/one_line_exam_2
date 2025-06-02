from bson import ObjectId
from datetime import datetime

class Result:
    def __init__(self, student_id, exam_id, score, answers, start_time=None):
        self.student_id = student_id
        self.exam_id = exam_id
        self.score = score
        self.answers = answers
        self.start_time = start_time or datetime.utcnow()
        self.status = 'in_progress'
        self._id = ObjectId()

    def to_dict(self):
        return {
            '_id': self._id,
            'student_id': self.student_id,
            'exam_id': self.exam_id,
            'score': self.score,
            'answers': self.answers,
            'start_time': self.start_time,
            'status': self.status
        }