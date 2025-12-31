from functools import wraps
from flask import g
from common.extensions import db, mongo_db
from common.saga.saga_orchestrator import SagaOrchestrator, SagaContext
from app.models.mongodb.saga_transaction_log import SagaTransactionLogRepository
from common.utils.logging_utils import get_logger
import uuid

logger = get_logger('db_decorators')


def union_transactional(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        transaction_id = str(uuid.uuid4())

        saga_context = SagaContext(transaction_id)
        g.saga_context = saga_context

        g.rdb_operations = []

        try:
            result = func(*args, **kwargs)

            db.session.commit()

            logger.info(f"Transaction {transaction_id} committed successfully")
            return result

        except Exception as e:
            logger.error(f"Transaction {transaction_id} failed: {e}")

            db.session.rollback()

            #NOTE: MongoDB 작업들은 각 Repository에서 자동으로 보상됨

            raise

        finally:
            if hasattr(g, 'saga_context'):
                delattr(g, 'saga_context')
            if hasattr(g, 'rdb_operations'):
                delattr(g, 'rdb_operations')

    return wrapper


def saga_transactional(
    rdb_operations=None,
    mongo_operations=None,
    metadata=None
):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            saga_repo = SagaTransactionLogRepository(mongo_db)

            orchestrator = SagaOrchestrator(
                saga_repo=saga_repo,
                metadata=metadata or {}
            )

            if rdb_operations:
                for name, execute_fn, compensate_fn, extract_fn in rdb_operations:
                    orchestrator.add_step(
                        name=name,
                        execute=execute_fn,
                        compensate=compensate_fn,
                        extract_compensation_data=extract_fn
                    )

            if mongo_operations:
                for name, execute_fn, compensate_fn, extract_fn in mongo_operations:
                    orchestrator.add_step(
                        name=name,
                        execute=execute_fn,
                        compensate=compensate_fn,
                        extract_compensation_data=extract_fn
                    )

            success, error = orchestrator.execute()

            if not success:
                raise error

            return func(*args, **kwargs)

        return wrapper

    return decorator


def transactional(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)

            db.session.commit()

            return result

        except Exception as e:
            db.session.rollback()
            raise

        finally:
            pass

    return wrapper


def transactional_readonly(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result

        except Exception as e:
            db.session.rollback()
            raise

        finally:
            pass

    return wrapper
