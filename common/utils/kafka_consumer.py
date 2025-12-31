import json
import logging
from typing import Callable, Dict, Any, Optional
from kafka import KafkaConsumer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)


class FacereviewKafkaConsumer:
    def __init__(self, bootstrap_servers: str, group_id: str, topics: list):
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.topics = topics
        self._consumer = None
        self._running = False

    def initialize(self):
        try:
            self._consumer = KafkaConsumer(
                *self.topics,
                bootstrap_servers=self.bootstrap_servers.split(','),
                group_id=self.group_id,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                auto_offset_reset='earliest',  # 가장 오래된 메시지부터
                enable_auto_commit=True,  # 자동 커밋
                auto_commit_interval_ms=1000,  # 1초마다 커밋
                session_timeout_ms=30000,  # 30초
                max_poll_records=100  # 한 번에 가져올 최대 레코드 수
            )
            logger.info(f"Kafka Consumer initialized: {self.bootstrap_servers}, Topics: {self.topics}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Kafka Consumer: {str(e)}")
            return False

    def consume(self, handler: Callable[[str, Dict[str, Any]], None]):
        if not self._consumer:
            logger.error("Consumer is not initialized. Call initialize() first.")
            return

        self._running = True
        logger.info(f"Starting Kafka Consumer for topics: {self.topics}")

        try:
            for message in self._consumer:
                if not self._running:
                    break

                try:
                    logger.debug(
                        f"Consumed message - Topic: {message.topic}, "
                        f"Partition: {message.partition}, Offset: {message.offset}"
                    )

                    # 핸들러 함수 호출
                    handler(message.topic, message.value)

                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
                    # 메시지 처리 실패해도 계속 진행 (DLQ로 보낼 수도 있음)

        except KafkaError as e:
            logger.error(f"Kafka error while consuming: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error while consuming: {str(e)}")
        finally:
            self.close()

    def stop(self):
        logger.info("Stopping Kafka Consumer...")
        self._running = False

    def close(self):
        if self._consumer:
            self._consumer.close()
            logger.info("Kafka Consumer closed")
            self._consumer = None


# 이벤트 핸들러 예시
def handle_user_event(topic: str, event_data: Dict[str, Any]):
    event_type = event_data.get('event_type')
    user_id = event_data.get('user_id')
    data = event_data.get('data', {})

    logger.info(f"Processing user event: {event_type} for user: {user_id}")

    # 이벤트 타입별 처리
    if event_type == 'signup':
        # 회원가입 이벤트 처리 (예: 환영 이메일 발송, 통계 업데이트 등)
        logger.info(f"New user signup: {user_id}")
        pass

    elif event_type == 'login':
        # 로그인 이벤트 처리
        logger.info(f"User login: {user_id}")
        pass

    elif event_type == 'profile_update':
        # 프로필 업데이트 이벤트 처리
        logger.info(f"User profile updated: {user_id}")
        pass

    else:
        logger.warning(f"Unknown event type: {event_type}")


def handle_video_event(topic: str, event_data: Dict[str, Any]):
    event_type = event_data.get('event_type')
    video_id = event_data.get('video_id')
    user_id = event_data.get('user_id')
    data = event_data.get('data', {})

    logger.info(f"Processing video event: {event_type} for video: {video_id}")

    # 이벤트 타입별 처리
    if event_type == 'view':
        # 시청 이벤트 처리 (예: 조회수 증가, 시청 기록 저장 등)
        logger.info(f"Video view: {video_id} by user: {user_id}")
        pass

    elif event_type == 'like':
        # 좋아요 이벤트 처리
        logger.info(f"Video like: {video_id} by user: {user_id}")
        pass

    elif event_type == 'comment':
        # 댓글 이벤트 처리
        logger.info(f"Video comment: {video_id} by user: {user_id}")
        pass

    else:
        logger.warning(f"Unknown event type: {event_type}")


def create_consumer_for_user_events(bootstrap_servers: str, group_id: str) -> FacereviewKafkaConsumer:
    consumer = FacereviewKafkaConsumer(
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        topics=['user-event']
    )
    return consumer


def create_consumer_for_video_events(bootstrap_servers: str, group_id: str) -> FacereviewKafkaConsumer:
    consumer = FacereviewKafkaConsumer(
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        topics=['video-event']
    )
    return consumer
