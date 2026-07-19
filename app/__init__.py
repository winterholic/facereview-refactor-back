import time
from flask import Flask, g
from flask_cors import CORS
from pymongo import MongoClient
from sqlalchemy.engine import URL
import redis
import logging
from common.extensions import db, socketio, api
import common.extensions as extensions
from common.celery_app import init_celery_app
from common.utils.logging_utils import setup_logger


def _register_blueprints(api_instance, include_development=False):
    from app.routes.base import base_blueprint
    from app.routes.auth import auth_blueprint, auth_test_blueprint
    from app.routes.home import home_blueprint
    from app.routes.mypage import mypage_blueprint
    from app.routes.watch import watch_blueprint
    from app.routes.admin import admin_blueprint

    for blueprint in (
        base_blueprint,
        auth_blueprint,
        home_blueprint,
        mypage_blueprint,
        watch_blueprint,
        admin_blueprint,
    ):
        api_instance.register_blueprint(blueprint)

    if include_development:
        from app.routes.test import test_blueprint
        api_instance.register_blueprint(auth_test_blueprint)
        api_instance.register_blueprint(test_blueprint)


def create_app(
    config_name='default',
    *,
    start_scheduler=True,
    preload_emotion_model=True,
):
    app = Flask(__name__)

    from common.config.config import config
    config_class = config.get(config_name, config['default'])
    app.config.from_object(config_class)

    app.json.ensure_ascii = False

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
         origins=app.config['CORS_ORIGINS'],
         allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With"],
         expose_headers=["Authorization", "Content-Type"],
         methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
         max_age=3600)

    socketio.init_app(
        app,
        cors_allowed_origins=app.config['CORS_ORIGINS'],
        logger=app.config['SOCKETIO_LOGGING'],
        engineio_logger=app.config['SOCKETIO_LOGGING'],
    )
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
            connectTimeoutMS=5000,
            minPoolSize=2,
            maxIdleTimeMS=60000
        )
        mongo_connection.admin.command('ping')
        logger.info(f"MongoDB 연결 성공: {mongo_host}:{mongo_port}")

        extensions.mongo_client = mongo_connection
        extensions.mongo_db = mongo_connection[app.config['MONGO_DB_NAME']]
        app.mongo = mongo_connection[app.config['MONGO_DB_NAME']]

        from app.models.mongodb.youtube_watching_data import YoutubeWatchingDataRepository
        YoutubeWatchingDataRepository.ensure_indexes(extensions.mongo_db)
        logger.info("MongoDB 인덱스 초기화 완료")

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

    if start_scheduler:
        from common.scheduler import init_scheduler
        init_scheduler(app)

    celery_obj = init_celery_app(app)
    extensions.celery = celery_obj
    _register_blueprints(
        api,
        include_development=app.config.get('ENABLE_DEVELOPMENT_ROUTES', False),
    )

    from common.exception.error_handler import register_error_handlers
    register_error_handlers(app)

    @app.before_request
    def _before_request():
        g.start_time = time.time()

    @app.after_request
    def _after_request(response):
        from common.extensions import redis_client as _redis
        if _redis:
            try:
                elapsed_ms = (time.time() - g.start_time) * 1000
                pipe = _redis.pipeline()
                pipe.incr('facereview:metrics:requests:1h')
                pipe.expire('facereview:metrics:requests:1h', 3600)
                pipe.lpush('facereview:metrics:response_times', elapsed_ms)
                pipe.ltrim('facereview:metrics:response_times', 0, 999)
                pipe.expire('facereview:metrics:response_times', 3600)
                if response.status_code >= 400:
                    pipe.incr('facereview:metrics:errors:1h')
                    pipe.expire('facereview:metrics:errors:1h', 3600)
                pipe.execute()
            except Exception:
                logger.debug("요청 메트릭 기록 실패", exc_info=True)
        return response

    @app.route('/health')
    def health_check():
        return {
            'status': 'healthy',
            'service': 'facereview'
        }, 200

    from app.sockets import video_watching_socket  # noqa: F401
    if preload_emotion_model:
        from app.sockets.video_watching_socket import get_emotion_analyzer
        get_emotion_analyzer()
        logger.info("EmotionAnalyzer 앱 시작 시 사전 로드 완료")

    return app
