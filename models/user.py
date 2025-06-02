from bson import ObjectId

class User:
    def __init__(self, name, email, password, role, student_id=None):
        self.name = name
        self.email = email
        self.password = password
        self.role = role
        self.student_id = student_id
        self._id = ObjectId()

    def to_dict(self):
        return {
            '_id': self._id,
            'name': self.name,
            'email': self.email,
            'password': self.password,
            'role': self.role,
            'student_id': self.student_id
        }