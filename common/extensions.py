from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_smorest import Api
from common.celery_app import celery_app

db = SQLAlchemy()

socketio = SocketIO()

api = Api()

redis_client = None

mongo_client = None
mongo_db = None

celery = celery_app
