from pymongo import MongoClient
import bcrypt
from config import Config

client = MongoClient(Config.MONGO_URI)
db = client['online_exam']
users_collection = db['users']

for user in users_collection.find({'role': 'student'}):
    stored_password = user['password']
    needs_fix = False
    if isinstance(stored_password, str):
        try:
            bcrypt.checkpw(b'test', stored_password.encode('utf-8'))
        except ValueError:
            needs_fix = True
            print(f"Invalid bcrypt hash detected for student: {user['email']}")
        else:
            needs_fix = True
            print(f"String password detected for student: {user['email']}")
    if needs_fix:
        new_password = stored_password if isinstance(stored_password, str) else 'default123'
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        users_collection.update_one(
            {'_id': user['_id']},
            {'$set': {'password': hashed_password}}
        )
        print(f"Fixed password for student: {user['email']}")
print("Student password fix completed.")