from bson import ObjectId
from datetime import datetime

class Exam:
    def __init__(self, title, duration, questions, created_by, scheduled_for, randomize, difficulty):
        self.title = title
        self.duration = duration
        self.questions = questions
        self.created_by = created_by
        self.scheduled_for = scheduled_for
        self.randomize = randomize
        self.difficulty = difficulty
        self.created_at = datetime.utcnow()
        self.status = 'scheduled'
        self._id = ObjectId()

    def to_dict(self):
        return {
            '_id': self._id,
            'title': self.title,
            'duration': self.duration,
            'questions': self.questions,
            'created_by': self.created_by,
            'scheduled_for': self.scheduled_for,
            'randomize': self.randomize,
            'difficulty': self.difficulty,
            'created_at': self.created_at,
            'status': self.status
        }