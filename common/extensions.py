from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_smorest import Api
from flask_apscheduler import APScheduler
from common.celery_app import celery_app

db = SQLAlchemy()

socketio = SocketIO(cors_allowed_origins="*")

api = Api()

redis_client = None

mongo_client = None
mongo_db = None

scheduler = APScheduler()

celery = celery_app

kafka_producer = None
