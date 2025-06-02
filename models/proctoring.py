from bson import ObjectId
import datetime

class ProctoringLog:
    def __init__(self, student_id, exam_id, event, timestamp):
        self.student_id = student_id
        self.exam_id = exam_id
        self.event = event
        self.timestamp = timestamp
        self._id = ObjectId()

    def to_dict(self):
        return {
            '_id': self._id,
            'student_id': self.student_id,
            'exam_id': self.exam_id,
            'event': self.event,
            'timestamp': self.timestamp
        }