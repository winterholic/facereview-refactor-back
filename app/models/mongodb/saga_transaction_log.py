from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class SagaStatus(str, Enum):
    PENDING = "pending"  # 시작 전
    IN_PROGRESS = "in_progress"  # 진행 중
    COMPLETED = "completed"  # 성공 완료
    COMPENSATING = "compensating"  # 보상 트랜잭션 실행 중
    COMPENSATED = "compensated"  # 보상 완료 (롤백 완료)
    FAILED = "failed"  # 실패 (보상 불가)


class StepStatus(str, Enum):
    PENDING = "pending"  # 실행 전
    COMPLETED = "completed"  # 성공
    FAILED = "failed"  # 실패
    COMPENSATED = "compensated"  # 보상 완료


@dataclass
class SagaStep:
    # 단계 이름 (예: "rdb_insert_video", "mongo_insert_watching_data")
    name: str

    # 단계 상태
    status: StepStatus = StepStatus.PENDING

    # 실행 시작/종료 시각
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 보상 트랜잭션 실행 시각
    compensated_at: Optional[datetime] = None

    # 에러 정보
    error_message: Optional[str] = None

    # 보상 트랜잭션에 필요한 데이터 (예: 삭제할 ID, 원래 값 등)
    compensation_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'status': self.status.value,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'compensated_at': self.compensated_at,
            'error_message': self.error_message,
            'compensation_data': self.compensation_data
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'SagaStep':
        return cls(
            name=data['name'],
            status=StepStatus(data.get('status', 'pending')),
            started_at=data.get('started_at'),
            completed_at=data.get('completed_at'),
            compensated_at=data.get('compensated_at'),
            error_message=data.get('error_message'),
            compensation_data=data.get('compensation_data', {})
        )


@dataclass
class SagaTransactionLog:
    # 트랜잭션 ID (UUID)
    transaction_id: str

    # 전체 사가 상태
    status: SagaStatus = SagaStatus.PENDING

    # 실행할 단계들 (순서 보장)
    steps: List[SagaStep] = field(default_factory=list)

    # 생성 시각
    created_at: datetime = field(default_factory=datetime.utcnow)

    # 완료 시각
    completed_at: Optional[datetime] = None

    # 보상 시작 시각
    compensation_started_at: Optional[datetime] = None

    # 보상 완료 시각
    compensation_completed_at: Optional[datetime] = None

    # 메타 데이터 (디버깅/추적용)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'transaction_id': self.transaction_id,
            'status': self.status.value,
            'steps': [step.to_dict() for step in self.steps],
            'created_at': self.created_at,
            'completed_at': self.completed_at,
            'compensation_started_at': self.compensation_started_at,
            'compensation_completed_at': self.compensation_completed_at,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'SagaTransactionLog':
        return cls(
            transaction_id=data['transaction_id'],
            status=SagaStatus(data.get('status', 'pending')),
            steps=[SagaStep.from_dict(step) for step in data.get('steps', [])],
            created_at=data.get('created_at', datetime.utcnow()),
            completed_at=data.get('completed_at'),
            compensation_started_at=data.get('compensation_started_at'),
            compensation_completed_at=data.get('compensation_completed_at'),
            metadata=data.get('metadata', {})
        )

    def add_step(self, step_name: str, compensation_data: Dict[str, Any] = None):
        step = SagaStep(
            name=step_name,
            compensation_data=compensation_data or {}
        )
        self.steps.append(step)

    def get_completed_steps(self) -> List[SagaStep]:
        return [step for step in self.steps if step.status == StepStatus.COMPLETED]

    def get_current_step_index(self) -> Optional[int]:
        for i, step in enumerate(self.steps):
            if step.status == StepStatus.PENDING:
                return i
        return None


class SagaTransactionLogRepository:
    COLLECTION_NAME = 'saga_transaction_log'

    def __init__(self, db):
        self.collection = db[self.COLLECTION_NAME]
        # NOTE : 인덱스 생성
        self.collection.create_index('transaction_id', unique=True)
        self.collection.create_index([('created_at', -1)])
        self.collection.create_index([('status', 1)])

    # NOTE : 사가 로그 생성
    def insert(self, saga_log: SagaTransactionLog):
        self.collection.insert_one(saga_log.to_dict())

    # NOTE : 트랜잭션 ID로 조회
    def find_by_transaction_id(self, transaction_id: str) -> Optional[SagaTransactionLog]:
        doc = self.collection.find_one({'transaction_id': transaction_id})
        return SagaTransactionLog.from_dict(doc) if doc else None

    # NOTE : 사가 상태 업데이트
    def update_status(self, transaction_id: str, status: SagaStatus):
        self.collection.update_one(
            {'transaction_id': transaction_id},
            {'$set': {'status': status.value}}
        )

    # NOTE : 특정 단계 업데이트
    def update_step(self, transaction_id: str, step_index: int, update_data: Dict):
        field_updates = {
            f'steps.{step_index}.{key}': value
            for key, value in update_data.items()
        }

        self.collection.update_one(
            {'transaction_id': transaction_id},
            {'$set': field_updates}
        )

    # NOTE : 단계를 완료로 표시
    def mark_step_completed(self, transaction_id: str, step_index: int):
        self.update_step(transaction_id, step_index, {
            'status': StepStatus.COMPLETED.value,
            'completed_at': datetime.utcnow()
        })

    # NOTE : 단계를 실패로 표시
    def mark_step_failed(self, transaction_id: str, step_index: int, error_message: str):
        self.update_step(transaction_id, step_index, {
            'status': StepStatus.FAILED.value,
            'error_message': error_message,
            'completed_at': datetime.utcnow()
        })

    # NOTE : 단계를 보상 완료로 표시
    def mark_step_compensated(self, transaction_id: str, step_index: int):
        self.update_step(transaction_id, step_index, {
            'status': StepStatus.COMPENSATED.value,
            'compensated_at': datetime.utcnow()
        })

    # NOTE : 보상 트랜잭션 시작
    def start_compensation(self, transaction_id: str):
        self.collection.update_one(
            {'transaction_id': transaction_id},
            {
                '$set': {
                    'status': SagaStatus.COMPENSATING.value,
                    'compensation_started_at': datetime.utcnow()
                }
            }
        )

    # NOTE : 보상 트랜잭션 완료
    def complete_compensation(self, transaction_id: str):
        self.collection.update_one(
            {'transaction_id': transaction_id},
            {
                '$set': {
                    'status': SagaStatus.COMPENSATED.value,
                    'compensation_completed_at': datetime.utcnow()
                }
            }
        )

    # NOTE : 사가 성공 완료
    def complete_saga(self, transaction_id: str):
        self.collection.update_one(
            {'transaction_id': transaction_id},
            {
                '$set': {
                    'status': SagaStatus.COMPLETED.value,
                    'completed_at': datetime.utcnow()
                }
            }
        )

    # NOTE : 사가 실패로 표시 (보상 불가능)
    def mark_failed(self, transaction_id: str):
        self.collection.update_one(
            {'transaction_id': transaction_id},
            {
                '$set': {
                    'status': SagaStatus.FAILED.value,
                    'completed_at': datetime.utcnow()
                }
            }
        )

    # NOTE : 오래된 로그 삭제 (기본 30일 이전)
    def delete_old_logs(self, days: int = 30):
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        self.collection.delete_many({
            'created_at': {'$lt': cutoff_date},
            'status': {'$in': [SagaStatus.COMPLETED.value, SagaStatus.COMPENSATED.value]}
        })
