import unittest
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask, g

from common.decorator.db_decorators import union_transactional
from common.saga.saga_orchestrator import SagaContext
from app.models.mongodb.video_distribution import (
    VideoDistribution,
    VideoDistributionRepository,
)
from app.models.mongodb.video_timeline_emotion_count import (
    VideoTimelineEmotionCount,
    VideoTimelineEmotionCountRepository,
)
from app.models.mongodb.youtube_watching_data import (
    YoutubeWatchingData,
    YoutubeWatchingDataRepository,
)
from app.models.user import User
from app.models.video import Video
from app.models.video_request import VideoRequest
from app.services.admin_service import AdminService
from common.enum.youtube_genre import GenreEnum
from common.extensions import db


class SagaContextTest(unittest.TestCase):
    def test_compensations_run_in_reverse_order(self):
        context = SagaContext('tx-1')
        calls = []
        context.add_compensation('first', lambda data: calls.append(data), 'first')
        context.add_compensation('second', lambda data: calls.append(data), 'second')

        context.compensate_all()

        self.assertEqual(calls, ['second', 'first'])

    def test_all_compensations_are_attempted_when_one_fails(self):
        from common.saga.saga_orchestrator import SagaCompensationError

        context = SagaContext('tx-2')
        calls = []

        def fail(data):
            calls.append(data)
            raise RuntimeError('compensation failed')

        context.add_compensation('first', lambda data: calls.append(data), 'first')
        context.add_compensation('second', fail, 'second')

        with self.assertRaises(SagaCompensationError):
            context.compensate_all()

        self.assertEqual(calls, ['second', 'first'])


class UnionTransactionalTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def test_commit_failure_rolls_back_sql_and_compensates_mongo(self):
        events = []
        session = SimpleNamespace(
            commit=lambda: (_ for _ in ()).throw(RuntimeError('commit failed')),
            rollback=lambda: events.append('sql-rollback'),
        )
        database = SimpleNamespace(session=session)

        @union_transactional
        def operation():
            events.append('mongo-write')
            g.saga_context.add_compensation(
                'undo-mongo',
                lambda data: events.append(data),
                'mongo-compensated',
            )

        with self.app.app_context(), patch('common.decorator.db_decorators.db', database):
            with self.assertRaisesRegex(RuntimeError, 'commit failed'):
                operation()

        self.assertEqual(events, [
            'mongo-write',
            'sql-rollback',
            'mongo-compensated',
        ])

    def test_successful_commit_does_not_compensate(self):
        events = []
        session = SimpleNamespace(
            commit=lambda: events.append('sql-commit'),
            rollback=lambda: events.append('sql-rollback'),
        )
        database = SimpleNamespace(session=session)

        @union_transactional
        def operation():
            g.saga_context.add_compensation(
                'undo-mongo',
                lambda data: events.append(data),
                'mongo-compensated',
            )

        with self.app.app_context(), patch('common.decorator.db_decorators.db', database):
            operation()

        self.assertEqual(events, ['sql-commit'])

    def test_compensation_failure_keeps_original_error_as_cause(self):
        session = SimpleNamespace(commit=MagicMock(), rollback=MagicMock())
        database = SimpleNamespace(session=session)

        @union_transactional
        def operation():
            def fail_compensation(_data):
                raise RuntimeError('compensation failed')

            g.saga_context.add_compensation(
                'undo-mongo',
                fail_compensation,
                None,
            )
            raise ValueError('business operation failed')

        with self.app.app_context(), patch('common.decorator.db_decorators.db', database):
            from common.saga.saga_orchestrator import SagaCompensationError

            with self.assertRaises(SagaCompensationError) as raised:
                operation()

        self.assertIsInstance(raised.exception.__cause__, ValueError)
        session.rollback.assert_called_once_with()


class MongoRepositoryCompensationTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def test_new_documents_register_delete_compensation(self):
        cases = [
            (
                VideoDistributionRepository,
                VideoDistribution(video_id='video-1'),
            ),
            (
                VideoTimelineEmotionCountRepository,
                VideoTimelineEmotionCount(video_id='video-1'),
            ),
        ]

        for repository_type, document in cases:
            with self.subTest(repository=repository_type.__name__):
                collection = MagicMock()
                collection.find_one.return_value = None
                mongo_database = MagicMock()
                mongo_database.__getitem__.return_value = collection
                context = SagaContext('tx-repository')

                with self.app.app_context():
                    g.saga_context = context
                    repository_type(mongo_database).upsert(document)
                    context.compensate_all()

                collection.delete_one.assert_called_once_with({'video_id': 'video-1'})

    def test_updated_distribution_is_restored_to_its_previous_value(self):
        previous = VideoDistribution(
            video_id='video-1',
            average_completion_rate=0.75,
        ).to_dict()
        collection = MagicMock()
        collection.find_one.return_value = previous
        mongo_database = MagicMock()
        mongo_database.__getitem__.return_value = collection
        context = SagaContext('tx-restore')

        with self.app.app_context():
            g.saga_context = context
            VideoDistributionRepository(mongo_database).upsert(
                VideoDistribution(
                    video_id='video-1',
                    average_completion_rate=0.25,
                )
            )
            context.compensate_all()

        collection.replace_one.assert_called_once_with(
            {'video_id': 'video-1'},
            previous,
        )
        collection.delete_one.assert_not_called()

    def test_new_watching_session_registers_delete_compensation(self):
        collection = MagicMock()
        mongo_database = MagicMock()
        mongo_database.__getitem__.return_value = collection
        context = SagaContext('tx-watching-data')
        watching_data = YoutubeWatchingData(
            user_id='user-1',
            video_id='video-1',
            video_view_log_id='view-1',
            created_at=datetime.utcnow(),
        )

        with self.app.app_context():
            g.saga_context = context
            YoutubeWatchingDataRepository(mongo_database).insert(watching_data)
            context.compensate_all()

        collection.delete_one.assert_called_once_with(
            {'video_view_log_id': 'view-1'}
        )

    def test_first_mongo_write_is_compensated_when_second_write_fails(self):
        distribution_collection = MagicMock()
        distribution_collection.find_one.return_value = None
        timeline_collection = MagicMock()
        timeline_collection.find_one.return_value = None
        timeline_collection.update_one.side_effect = RuntimeError('timeline failed')
        mongo_database = {
            'video_distribution': distribution_collection,
            'video_timeline_emotion_count': timeline_collection,
        }
        session = SimpleNamespace(commit=MagicMock(), rollback=MagicMock())
        database = SimpleNamespace(session=session)

        @union_transactional
        def operation():
            VideoDistributionRepository(mongo_database).upsert(
                VideoDistribution(video_id='video-1')
            )
            VideoTimelineEmotionCountRepository(mongo_database).upsert(
                VideoTimelineEmotionCount(video_id='video-1')
            )

        with self.app.app_context(), patch('common.decorator.db_decorators.db', database):
            with self.assertRaisesRegex(RuntimeError, 'timeline failed'):
                operation()

        distribution_collection.delete_one.assert_called_once_with(
            {'video_id': 'video-1'}
        )
        session.commit.assert_not_called()
        session.rollback.assert_called_once_with()


class CrossDatabaseWorkflowBoundaryTest(unittest.TestCase):
    def test_admin_video_approval_uses_compensating_transaction(self):
        source = Path('app/services/admin_service.py').read_text(encoding='utf-8')
        decorator_position = source.index('@union_transactional')
        method_position = source.index('def approve_video_request')

        self.assertLess(decorator_position, method_position)

    def test_admin_dummy_session_uses_compensating_transaction(self):
        source = Path('app/services/admin_service.py').read_text(encoding='utf-8')

        self.assertIn('@union_transactional\n    def _save_dummy_session', source)

    def test_youtube_collectors_commit_each_video_with_compensation(self):
        trending = Path(
            'common/scheduler/jobs/youtube_trending_job.py'
        ).read_text(encoding='utf-8')
        category = Path(
            'common/scheduler/jobs/youtube_category_fill_job.py'
        ).read_text(encoding='utf-8')

        self.assertIn('@union_transactional\n    def _save_video', trending)
        self.assertIn('@union_transactional\n    def _save_video', category)


class AdminApprovalCompensationIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            MONGO_DB_NAME='test-mongo',
        )
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        user = User(
            user_id='user-1',
            email='user@example.com',
            password='password',
            name='tester',
        )
        request = VideoRequest(
            video_request_id='request-1',
            user_id='user-1',
            youtube_url='youtube-1',
            youtube_full_url='https://www.youtube.com/watch?v=youtube-1',
            status='PENDING',
        )
        db.session.add_all([user, request])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_sql_commit_failure_removes_both_mongo_documents(self):
        distribution_collection = MagicMock()
        distribution_collection.find_one.return_value = None
        timeline_collection = MagicMock()
        timeline_collection.find_one.return_value = None
        mongo_database = {
            'video_distribution': distribution_collection,
            'video_timeline_emotion_count': timeline_collection,
        }
        mongo_client = {'test-mongo': mongo_database}

        with (
            patch('app.services.admin_service.mongo_client', mongo_client),
            patch.object(
                db.session,
                'commit',
                side_effect=RuntimeError('commit failed'),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, 'commit failed'):
                AdminService.approve_video_request(
                    'request-1',
                    'title',
                    'channel',
                    120,
                    GenreEnum.ETC.value,
                )

        self.assertIsNone(Video.query.filter_by(youtube_url='youtube-1').first())
        request = VideoRequest.query.filter_by(
            video_request_id='request-1'
        ).first()
        self.assertEqual(request.status, 'PENDING')
        distribution_collection.delete_one.assert_called_once()
        timeline_collection.delete_one.assert_called_once()


if __name__ == '__main__':
    unittest.main()
