from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_smorest import Api
from flask_apscheduler import APScheduler
from common.celery_app import celery_app
import logging

db = SQLAlchemy()

socketio = SocketIO(
    cors_allowed_origins="*",
    logger=True,          # SocketIO 이벤트 로그
    engineio_logger=True  # 연결 / 핸드셰이크 로그
)

api = Api()

redis_client = None

mongo_client = None
mongo_db = None

scheduler = APScheduler()

celery = celery_app

kafka_producer = None
