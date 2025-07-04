from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from routes.auth import auth_bp
from routes.exam import exam_bp
from routes.proctoring import proctoring_bp
from routes.queries import queries_bp
from config import Config
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)

# Configure CORS to allow requests from the Vercel frontend
CORS(app, resources={r"/api/*": {"origins": ["https://online-exam-system-nine.vercel.app"], "supports_credentials": True}})

# Load configuration
app.config.from_object(Config)
jwt = JWTManager(app)
mail = Mail(app)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/api')
app.register_blueprint(exam_bp, url_prefix='/api')
app.register_blueprint(proctoring_bp, url_prefix='/api')
app.register_blueprint(queries_bp, url_prefix='/api')

logger.info("Flask application started")

if __name__ == '__main__':
    app.run(debug=True, port=5000)