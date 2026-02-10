"""
Face Review Application
Flask 기반 얼굴 인식 웹 애플리케이션
"""

from flask import Flask
from flask_cors import CORS
from pymongo import MongoClient
from sqlalchemy.engine import URL
import redis
import logging
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from common.extensions import db, socketio, api, celery
import common.extensions as extensions
from common.celery_app import create_celery_app
from common.utils.logging_utils import setup_logger


def create_app(config_name='default'):
    """
    Application Factory Pattern
    """
    app = Flask(__name__)

    from common.config.config import config
    config_class = config.get(config_name, config['default'])
    app.config.from_object(config_class)

    app.json.ensure_ascii = False

    if app.config.get('SENTRY_DSN'):
        sentry_sdk.init(
            dsn=app.config['SENTRY_DSN'],
            integrations=[
                FlaskIntegration(),
                SqlalchemyIntegration(),
                RedisIntegration(),
                CeleryIntegration(),
            ],
            environment=app.config.get('SENTRY_ENVIRONMENT', 'development'),
            traces_sample_rate=app.config.get('SENTRY_TRACES_SAMPLE_RATE', 1.0),
            send_default_pii=False,
            attach_stacktrace=True,
            before_send=lambda event, hint: event if app.config.get('FLASK_ENV') != 'development' or app.config.get('SENTRY_DSN') else None,
        )

    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO'))
    logger = setup_logger(app, log_level)

    if not app.config.get('TESTING'):
        required = [
            'DB_USERNAME', 'DB_PASSWORD',
            'DB_HOST', 'DB_PORT', 'DB_NAME'
        ]
        missing = [k for k in required if not app.config.get(k)]
        if missing:
            raise RuntimeError(f"DB 환경변수 누락: {missing}")

        app.config['SQLALCHEMY_DATABASE_URI'] = URL.create(
            drivername='mysql+pymysql',
            username=app.config['DB_USERNAME'],
            password=app.config['DB_PASSWORD'],
            host=app.config['DB_HOST'],
            port=app.config['DB_PORT'],
            database=app.config['DB_NAME'],
        )
    app.config['API_TITLE'] = 'FaceReview API'
    app.config['API_VERSION'] = 'v2'
    app.config['OPENAPI_VERSION'] = '3.0.3'
    app.config['OPENAPI_URL_PREFIX'] = '/'
    app.config['OPENAPI_SWAGGER_UI_PATH'] = '/swagger'
    app.config['OPENAPI_SWAGGER_UI_URL'] = 'https://cdn.jsdelivr.net/npm/swagger-ui-dist/'
    app.config['OPENAPI_REDOC_PATH'] = '/redoc'
    app.config['OPENAPI_REDOC_URL'] = 'https://cdn.jsdelivr.net/npm/redoc@latest/bundles/redoc.standalone.js'

    # JWT Bearer 토큰 인증을 위한 보안 스킴 설정
    app.config['API_SPEC_OPTIONS'] = {
        'components': {
            'securitySchemes': {
                'BearerAuth': {
                    'type': 'http',
                    'scheme': 'bearer',
                    'bearerFormat': 'JWT',
                    'description': 'JWT 액세스 토큰을 입력하세요 (Bearer 접두어 없이)'
                }
            }
        }
    }

    db.init_app(app)
    CORS(app,
         supports_credentials=True,
         origins=["localhost:3000", "localhost:5173", "localhost:4173", "localhost:5000",
         "https://facereview-api.winterholic.net"],  # TODO "https://frontdomain.com", "https://admin.frontdomain.com" 이런식으로 수정필요
         allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With"],
         expose_headers=["Authorization", "Content-Type"],
         methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
         max_age=3600)

    socketio.init_app(app)
    api.init_app(app)

    mongo_host = app.config.get('MONGO_HOST', 'localhost')
    mongo_port = app.config.get('MONGO_PORT', 27017)
    mongo_username = app.config.get('MONGO_USERNAME')
    mongo_password = app.config.get('MONGO_PASSWORD')

    if mongo_username and mongo_password:
        from urllib.parse import quote_plus
        mongo_uri = f"mongodb://{quote_plus(mongo_username)}:{quote_plus(mongo_password)}@{mongo_host}:{mongo_port}/"
    else:
        mongo_uri = f"mongodb://{mongo_host}:{mongo_port}/"

    logger.info(f"MongoDB 연결 시도: {mongo_host}:{mongo_port}")

    try:
        mongo_connection = MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000
        )
        mongo_connection.admin.command('ping')
        logger.info(f"MongoDB 연결 성공: {mongo_host}:{mongo_port}")

        extensions.mongo_client = mongo_connection
        extensions.mongo_db = mongo_connection[app.config['MONGO_DB_NAME']]
        app.mongo = mongo_connection[app.config['MONGO_DB_NAME']]

    except Exception as e:
        logger.error(f"MongoDB 연결 실패: {e}")
        logger.error(f"MongoDB URI (마스킹): mongodb://{mongo_host}:{mongo_port}/")
        raise

    try:
        if app.config.get('REDIS_URL'):
            redis_url = app.config['REDIS_URL']
            logger.info("Redis 연결 시도: REDIS_URL 사용")
            extensions.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5
            )
        else:
            redis_host = app.config.get('REDIS_HOST', 'localhost')
            redis_port = app.config.get('REDIS_PORT', 6379)
            redis_db = app.config.get('REDIS_DB', 0)
            redis_password = app.config.get('REDIS_PASSWORD')

            if redis_password == "":
                redis_password = None

            logger.info(f"Redis 연결 시도: {redis_host}:{redis_port} (db={redis_db}, 인증={'설정됨' if redis_password else '없음'})")

            extensions.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )

        extensions.redis_client.ping()
        logger.info("Redis 연결 성공")

    except redis.ConnectionError as e:
        logger.warning(f"Redis 연결 실패: {e}")
        logger.warning("Redis 기능(캐싱, 세션 등)이 비활성화됩니다")
        extensions.redis_client = None
    except redis.AuthenticationError as e:
        logger.warning(f"Redis 인증 실패: {e}")
        logger.warning("Redis 설정에서 REDIS_PASSWORD를 확인하세요")
        extensions.redis_client = None
    except Exception as e:
        logger.warning(f"Redis 초기화 중 예상치 못한 오류 발생: {e}")
        logger.exception("상세 오류 정보:")
        extensions.redis_client = None

    from common.utils.kafka_producer import FacereviewKafkaProducer
    kafka_producer_instance = FacereviewKafkaProducer(
        bootstrap_servers=app.config.get('KAFKA_BOOTSTRAP_SERVERS'),
        client_id=app.config.get('KAFKA_CLIENT_ID')
    )
    extensions.kafka_producer = kafka_producer_instance

    from common.scheduler import init_scheduler
    init_scheduler(app)

    celery_obj = create_celery_app(app)
    extensions.celery = celery_obj
    from app.routes.base import base_blueprint
    from app.routes.auth import auth_blueprint
    from app.routes.home import home_blueprint
    from app.routes.mypage import mypage_blueprint
    from app.routes.watch import watch_blueprint
    from app.routes.admin import admin_blueprint
    from app.routes.test import test_blueprint

    api.register_blueprint(base_blueprint)
    api.register_blueprint(auth_blueprint)
    api.register_blueprint(home_blueprint)
    api.register_blueprint(mypage_blueprint)
    api.register_blueprint(watch_blueprint)
    api.register_blueprint(admin_blueprint)
    api.register_blueprint(test_blueprint)

    from common.exception.error_handler import register_error_handlers
    register_error_handlers(app)
    @app.route('/health')
    def health_check():
        return {
            'status': 'healthy',
            'service': 'facereview'
        }, 200

    from app.sockets import video_watching_socket

    return app
