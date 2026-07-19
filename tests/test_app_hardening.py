import importlib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from celery import Celery
from flask import Flask, current_app, g

import app as app_package
import common.celery_app as celery_module
import common.config.celery_config as celery_config_module
import common.decorator.auth_decorators as auth_decorators
from app.routes.base import base_endpoint
from common.enum.error_code import APIError
from common.exception.error_handler import register_error_handlers
from common.exception.exceptions import BusinessError
from common.utils.jwt_utils import create_access_token, create_refresh_token
from sqlalchemy.exc import IntegrityError
from sqlalchemy import create_engine

from common.extensions import db
from common.config.config import ProductionConfig
from common.config.celery_config import CeleryConfig
from app.models.user import User
from app.services.auth_service import AuthService
from werkzeug.security import generate_password_hash


class AuthenticationHeaderTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=False,
            JWT_SECRET_KEY='test-secret',
        )
        register_error_handlers(self.app)

        from common.decorator.auth_decorators import login_required, login_optional

        @self.app.get('/required')
        @login_required
        def required_route():
            return {'user_id': g.user_id}

        @self.app.get('/optional')
        @login_optional
        def optional_route():
            return {'is_guest': g.is_guest}

        self.client = self.app.test_client()

    def test_required_route_rejects_empty_bearer_token(self):
        response = self.client.get('/required', headers={'Authorization': 'Bearer '})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()['code'], APIError.AUTH_INVALID_TOKEN.code)

    def test_required_route_rejects_extra_authorization_parts(self):
        with self.app.app_context():
            token = create_access_token('user-1')

        response = self.client.get(
            '/required',
            headers={'Authorization': f'Bearer {token} extra'},
        )

        self.assertEqual(response.status_code, 401)

    def test_optional_route_rejects_empty_bearer_token(self):
        response = self.client.get('/optional', headers={'Authorization': 'Bearer '})

        self.assertEqual(response.status_code, 401)

    def test_required_route_rejects_token_from_current_redis_blacklist(self):
        with self.app.app_context():
            token = create_access_token('user-1')
        redis = SimpleNamespace(exists=lambda key: True)

        with patch('common.extensions.redis_client', redis):
            response = self.client.get(
                '/required',
                headers={'Authorization': f'Bearer {token}'},
            )

        self.assertEqual(response.status_code, 401)

    def test_required_route_rejects_deactivated_user(self):
        with self.app.app_context():
            token = create_access_token('user-1')
        query = SimpleNamespace(
            filter_by=lambda **kwargs: SimpleNamespace(first=lambda: None)
        )
        database = SimpleNamespace(session=SimpleNamespace(query=lambda model: query))

        with patch('common.extensions.db', database):
            response = self.client.get(
                '/required',
                headers={'Authorization': f'Bearer {token}'},
            )

        self.assertEqual(response.status_code, 401)


class ErrorResponseTest(unittest.TestCase):
    def test_database_error_is_server_error(self):
        self.assertEqual(APIError.DB_ERROR.status, 500)

    def test_integrity_error_uses_common_response_shape(self):
        app = Flask(__name__)
        app.config['TESTING'] = False
        register_error_handlers(app)

        @app.get('/integrity-error')
        def integrity_error():
            raise IntegrityError('statement', {}, Exception('duplicate'))

        response = app.test_client().get('/integrity-error')

        self.assertEqual(response.status_code, 400)
        self.assertIsNone(response.get_json()['data'])

    def test_unknown_route_preserves_not_found_status(self):
        app = Flask(__name__)
        app.config['TESTING'] = False
        register_error_handlers(app)

        response = app.test_client().get('/missing')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()['code'], 'C004')


class PublicEndpointTest(unittest.TestCase):
    def test_base_endpoint_does_not_require_an_injected_argument(self):
        with Flask(__name__).test_request_context('/'):
            response = base_endpoint()

        self.assertEqual(response['status'], 'ok')


class TestingDatabaseCompatibilityTest(unittest.TestCase):
    def test_models_can_create_schema_on_configured_sqlite_test_database(self):
        engine = create_engine('sqlite:///:memory:')

        db.metadata.create_all(engine)


class DeactivatedUserAuthenticationTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask('auth-test')
        self.app.config.update(
            SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            JWT_SECRET_KEY='test-secret',
        )
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        user = User(
            email='deleted@example.com',
            password=generate_password_hash('password123'),
            name='탈퇴회원',
            is_deleted=True,
        )
        db.session.add(user)
        db.session.commit()
        self.user_id = user.user_id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_deactivated_user_cannot_log_in(self):
        with self.assertRaises(BusinessError) as raised:
            AuthService.login('deleted@example.com', 'password123')

        self.assertIs(raised.exception.error_enum, APIError.AUTH_INVALID_EMAIL)

    def test_deactivated_user_cannot_reissue_tokens(self):
        refresh_token = create_refresh_token(self.user_id)

        with self.assertRaises(BusinessError) as raised:
            AuthService.reissue(refresh_token)

        self.assertIs(raised.exception.error_enum, APIError.USER_NOT_FOUND)

    def test_deactivated_user_cannot_read_profile(self):
        with self.assertRaises(BusinessError) as raised:
            AuthService.get_my_info(self.user_id)

        self.assertIs(raised.exception.error_enum, APIError.USER_NOT_FOUND)


class AdminAuthorizationTest(unittest.TestCase):
    def test_admin_guard_uses_forbidden_error_for_general_user(self):
        admin_required = getattr(auth_decorators, 'admin_required', None)
        self.assertTrue(callable(admin_required))
        app = Flask(__name__)
        with app.test_request_context('/'):
            g.user_id = 'user-1'
            g.current_user = SimpleNamespace(role='GENERAL')
            with self.assertRaises(BusinessError) as raised:
                admin_required(lambda: None)()

        self.assertIs(raised.exception.error_enum, APIError.USER_FORBIDDEN)

    def test_super_admin_guard_uses_forbidden_error_for_admin(self):
        super_admin_required = getattr(auth_decorators, 'super_admin_required', None)
        self.assertTrue(callable(super_admin_required))
        app = Flask(__name__)
        with app.test_request_context('/'):
            g.user_id = 'user-1'
            g.current_user = SimpleNamespace(role='ADMIN')
            with self.assertRaises(BusinessError) as raised:
                super_admin_required(lambda: None)()

        self.assertIs(raised.exception.error_enum, APIError.USER_FORBIDDEN)


class BlueprintRegistrationTest(unittest.TestCase):
    class _RecordingApi:
        def __init__(self):
            self.names = []

        def register_blueprint(self, blueprint):
            self.names.append(blueprint.name)

    def test_production_registration_excludes_development_blueprints(self):
        register_blueprints = getattr(app_package, '_register_blueprints', None)
        self.assertTrue(callable(register_blueprints))
        api = self._RecordingApi()

        register_blueprints(api, include_development=False)

        self.assertNotIn('test', api.names)
        self.assertNotIn('auth_test', api.names)

    def test_development_registration_includes_development_blueprints(self):
        register_blueprints = getattr(app_package, '_register_blueprints', None)
        self.assertTrue(callable(register_blueprints))
        api = self._RecordingApi()

        register_blueprints(api, include_development=True)

        self.assertIn('test', api.names)
        self.assertIn('auth_test', api.names)


class CorsConfigurationTest(unittest.TestCase):
    def test_production_origins_are_explicit_and_include_main_site(self):
        origins = ProductionConfig.CORS_ORIGINS

        self.assertIn('https://www.facereview.net', origins)
        self.assertNotIn('*', origins)

    def test_production_disables_socket_protocol_debug_logs(self):
        self.assertFalse(ProductionConfig.SOCKETIO_LOGGING)


class CeleryInitializationTest(unittest.TestCase):
    def test_initialized_tasks_execute_inside_flask_context(self):
        init_celery_app = getattr(celery_module, 'init_celery_app', None)
        self.assertTrue(callable(init_celery_app))
        flask_app = Flask('celery-test')
        celery = Celery('celery-test', broker='memory://', backend='cache+memory://')

        initialized = init_celery_app(flask_app, celery)

        @initialized.task
        def get_app_name():
            return current_app.name

        self.assertEqual(get_app_name.apply().get(), 'celery-test')

    def test_reinitializing_same_app_does_not_wrap_task_twice(self):
        flask_app = Flask('celery-test')
        celery = Celery('celery-test', broker='memory://', backend='cache+memory://')

        celery_module.init_celery_app(flask_app, celery)
        first_task_class = celery.Task
        celery_module.init_celery_app(flask_app, celery)

        self.assertIs(celery.Task, first_task_class)

    def test_worker_factory_disables_model_preload(self):
        create_worker_celery = getattr(celery_module, 'create_worker_celery', None)
        self.assertTrue(callable(create_worker_celery))
        calls = []

        def app_factory(config_name, **kwargs):
            calls.append((config_name, kwargs))
            return Flask('worker-test')

        celery = Celery('worker-test', broker='memory://', backend='cache+memory://')
        create_worker_celery(app_factory, 'production', celery)

        self.assertEqual(calls, [(
            'production',
            {'preload_emotion_model': False},
        )])

    def test_compose_uses_initialized_worker_module(self):
        compose = Path('docker-compose.yml').read_text(encoding='utf-8')

        self.assertIn(
            'celery -A celery_worker.celery worker --loglevel=info '
            '--queues=celery,watching_data',
            compose,
        )


class CeleryBeatConfigurationTest(unittest.TestCase):
    def test_celery_redis_url_falls_back_to_authenticated_components(self):
        build_redis_url = getattr(celery_config_module, 'build_redis_url', None)
        self.assertTrue(callable(build_redis_url))

        url = build_redis_url({
            'REDIS_HOST': 'redis.internal',
            'REDIS_PORT': '6380',
            'REDIS_DB': '3',
            'REDIS_PASSWORD': 'p@ss word',
        })

        self.assertEqual(url, 'redis://:p%40ss%20word@redis.internal:6380/3')

    def test_celery_redis_url_prefers_explicit_url(self):
        build_redis_url = getattr(celery_config_module, 'build_redis_url', None)
        self.assertTrue(callable(build_redis_url))

        url = build_redis_url({
            'REDIS_URL': 'redis://:secret@redis.example:6379/5',
            'REDIS_HOST': 'ignored',
        })

        self.assertEqual(url, 'redis://:secret@redis.example:6379/5')

    def test_periodic_jobs_are_registered_in_celery_beat(self):
        schedules = CeleryConfig.beat_schedule

        self.assertEqual(set(schedules), {
            'fetch-youtube-trending-videos',
            'fill-youtube-category-videos',
            'rebuild-recommendation-pool',
        })
        self.assertEqual(
            schedules['fetch-youtube-trending-videos']['task'],
            'common.tasks.scheduled_tasks.fetch_youtube_trending_videos',
        )

    def test_compose_runs_one_dedicated_beat_service(self):
        compose = Path('docker-compose.yml').read_text(encoding='utf-8')

        self.assertEqual(compose.count('celery-beat:'), 1)
        self.assertIn(
            'celery -A common.celery_app.celery_app beat --loglevel=info',
            compose,
        )
        self.assertEqual(compose.count('disable: true'), 2)

    def test_web_application_no_longer_imports_apscheduler(self):
        app_factory = Path('app/__init__.py').read_text(encoding='utf-8')
        extensions = Path('common/extensions.py').read_text(encoding='utf-8')

        self.assertNotIn('init_scheduler', app_factory)
        self.assertNotIn('APScheduler', extensions)

    def test_scheduled_tasks_are_discovered_by_celery(self):
        self.assertIn(
            'common.tasks.scheduled_tasks',
            celery_module.celery_app.conf.include,
        )

    def test_periodic_task_wrappers_execute_existing_business_jobs(self):
        try:
            scheduled_tasks = importlib.import_module('common.tasks.scheduled_tasks')
        except ModuleNotFoundError:
            self.fail('Celery Beat 작업 모듈이 필요합니다.')

        with patch.object(scheduled_tasks, 'YoutubeTrendingJob') as trending:
            scheduled_tasks.fetch_youtube_trending_videos.run()
            trending.return_value.execute.assert_called_once_with()

        with patch.object(scheduled_tasks, 'YoutubeCategoryFillJob') as category:
            scheduled_tasks.fill_youtube_category_videos.run()
            category.return_value.execute.assert_called_once_with()

        with patch.object(scheduled_tasks.HomeService, '_build_and_cache_ranked_pool') as rebuild:
            rebuild.return_value = (['video-1'], None)
            result = scheduled_tasks.rebuild_recommendation_pool.run()

        rebuild.assert_called_once_with()
        self.assertEqual(result, {'video_count': 1})


if __name__ == '__main__':
    unittest.main()
