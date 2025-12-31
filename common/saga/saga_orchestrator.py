import uuid
from typing import Callable, List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from common.utils.logging_utils import get_logger

from app.models.mongodb.saga_transaction_log import (
    SagaTransactionLog,
    SagaTransactionLogRepository,
    SagaStatus,
    SagaStep,
    StepStatus
)

logger = get_logger('saga_orchestrator')


@dataclass
class SagaStepDefinition:
    name: str
    execute: Callable
    compensate: Callable
    extract_compensation_data: Optional[Callable] = None


class SagaOrchestrator:

    def __init__(
        self,
        saga_repo: SagaTransactionLogRepository,
        transaction_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.saga_repo = saga_repo
        self.transaction_id = transaction_id or str(uuid.uuid4())
        self.metadata = metadata or {}
        self.steps: List[SagaStepDefinition] = []

        # 사가 로그 초기화
        self.saga_log = SagaTransactionLog(
            transaction_id=self.transaction_id,
            status=SagaStatus.PENDING,
            metadata=self.metadata
        )

    def add_step(
        self,
        name: str,
        execute: Callable,
        compensate: Callable,
        extract_compensation_data: Optional[Callable] = None
    ):
        step_def = SagaStepDefinition(
            name=name,
            execute=execute,
            compensate=compensate,
            extract_compensation_data=extract_compensation_data
        )
        self.steps.append(step_def)

        # 로그에도 단계 추가 (초기 상태)
        self.saga_log.add_step(step_name=name)

    def execute(self) -> Tuple[bool, Any]:
        logger.info(f"Starting transaction: {self.transaction_id}")

        # 사가 로그 저장
        self.saga_log.status = SagaStatus.IN_PROGRESS
        self.saga_repo.insert(self.saga_log)

        executed_steps: List[Tuple[int, SagaStepDefinition, Any, Dict[str, Any]]] = []

        try:
            # 각 단계 순차 실행
            for i, step_def in enumerate(self.steps):
                logger.debug(f"Executing step {i + 1}/{len(self.steps)}: {step_def.name}")

                # 단계 시작 기록
                self.saga_repo.update_step(
                    self.transaction_id,
                    i,
                    {
                        'status': StepStatus.PENDING.value,
                        'started_at': datetime.utcnow()
                    }
                )

                try:
                    # 단계 실행
                    result = step_def.execute()

                    # 보상 데이터 추출
                    compensation_data = {}
                    if step_def.extract_compensation_data:
                        compensation_data = step_def.extract_compensation_data(result)

                    # 실행된 단계 기록 (보상용)
                    executed_steps.append((i, step_def, result, compensation_data))

                    # 단계 완료 기록
                    self.saga_repo.update_step(
                        self.transaction_id,
                        i,
                        {
                            'status': StepStatus.COMPLETED.value,
                            'completed_at': datetime.utcnow(),
                            'compensation_data': compensation_data
                        }
                    )

                    logger.debug(f"Step {i + 1} completed: {step_def.name}")

                except Exception as step_error:
                    logger.error(f"Step {i + 1} failed: {step_def.name} - {step_error}")

                    # 단계 실패 기록
                    self.saga_repo.mark_step_failed(
                        self.transaction_id,
                        i,
                        str(step_error)
                    )

                    # 보상 트랜잭션 시작
                    self._compensate(executed_steps)

                    raise step_error

            # 모든 단계 성공
            logger.info(f"Transaction completed successfully: {self.transaction_id}")
            self.saga_repo.complete_saga(self.transaction_id)

            return True, None

        except Exception as e:
            logger.error(f"Transaction failed: {self.transaction_id} - {e}")
            return False, e

    def _compensate(self, executed_steps: List[Tuple[int, SagaStepDefinition, Any, Dict[str, Any]]]):
        logger.warning(f"Starting compensation for {len(executed_steps)} steps")

        # 보상 시작 기록
        self.saga_repo.start_compensation(self.transaction_id)

        # 역순으로 보상 실행
        for i, step_def, result, compensation_data in reversed(executed_steps):
            try:
                logger.debug(f"Compensating step: {step_def.name}")

                # 보상 함수 실행
                step_def.compensate(compensation_data)

                # 보상 완료 기록
                self.saga_repo.mark_step_compensated(self.transaction_id, i)

                logger.debug(f"Step compensated: {step_def.name}")

            except Exception as comp_error:
                logger.error(f"Compensation failed for {step_def.name}: {comp_error}")

                # NOTE: 보상 실패는 심각한 문제 - 수동 개입 필요
                self.saga_repo.mark_failed(self.transaction_id)
                raise Exception(
                    f"CRITICAL: Compensation failed for step '{step_def.name}'. "
                    f"Manual intervention required. Transaction ID: {self.transaction_id}"
                ) from comp_error

        # 보상 완료
        self.saga_repo.complete_compensation(self.transaction_id)
        logger.warning(f"Compensation completed: {self.transaction_id}")


class SagaContext:

    def __init__(self, transaction_id: str):
        self.transaction_id = transaction_id
        self.step_results: Dict[str, Any] = {}  # 각 단계의 결과 저장

    def save_result(self, step_name: str, result: Any):
        """단계 결과 저장"""
        self.step_results[step_name] = result

    def get_result(self, step_name: str) -> Any:
        """단계 결과 조회"""
        return self.step_results.get(step_name)
