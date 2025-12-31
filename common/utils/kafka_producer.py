import json
import logging
from typing import Dict, Any, Optional
from kafka import KafkaProducer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)


class FacereviewKafkaProducer:

    _instance = None
    _producer = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, bootstrap_servers: str = None, client_id: str = None):
        if self._producer is None and bootstrap_servers:
            try:
                self._producer = KafkaProducer(
                    bootstrap_servers=bootstrap_servers.split(','),
                    client_id=client_id,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    key_serializer=lambda k: k.encode('utf-8') if k else None,
                    acks='all',  # 모든 replica 확인
                    retries=3,  # 재시도 횟수
                    max_in_flight_requests_per_connection=1,  # 순서 보장
                    compression_type='gzip'  # 압축
                )
                logger.info(f"Kafka Producer initialized: {bootstrap_servers}")
            except Exception as e:
                logger.error(f"Failed to initialize Kafka Producer: {str(e)}")
                self._producer = None

    def send_event(self, topic: str, event_data: Dict[str, Any], key: Optional[str] = None) -> bool:
        if not self._producer:
            logger.warning("Kafka Producer is not initialized. Skipping event.")
            return False

        try:
            future = self._producer.send(topic, value=event_data, key=key)
            # 블로킹 방식으로 전송 완료 대기 (timeout 5초)
            record_metadata = future.get(timeout=5)
            logger.info(
                f"Event sent to Kafka - Topic: {record_metadata.topic}, "
                f"Partition: {record_metadata.partition}, Offset: {record_metadata.offset}"
            )
            return True
        except KafkaError as e:
            logger.error(f"Failed to send event to Kafka: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error while sending event: {str(e)}")
            return False

    def send_event_async(self, topic: str, event_data: Dict[str, Any],
                         key: Optional[str] = None,
                         callback=None) -> bool:
        if not self._producer:
            logger.warning("Kafka Producer is not initialized. Skipping event.")
            return False

        try:
            def on_send_success(record_metadata):
                logger.info(
                    f"Event sent to Kafka (async) - Topic: {record_metadata.topic}, "
                    f"Partition: {record_metadata.partition}, Offset: {record_metadata.offset}"
                )
                if callback:
                    callback(True, record_metadata)

            def on_send_error(exception):
                logger.error(f"Failed to send event to Kafka (async): {str(exception)}")
                if callback:
                    callback(False, exception)

            self._producer.send(topic, value=event_data, key=key)\
                .add_callback(on_send_success)\
                .add_errback(on_send_error)

            return True
        except Exception as e:
            logger.error(f"Unexpected error while sending event async: {str(e)}")
            return False

    def flush(self):
        """버퍼에 남아있는 모든 메시지 전송"""
        if self._producer:
            self._producer.flush()
            logger.info("Kafka Producer flushed")

    def close(self):
        """Kafka Producer 종료"""
        if self._producer:
            self._producer.close()
            logger.info("Kafka Producer closed")
            self._producer = None


# 글로벌 인스턴스
kafka_producer = FacereviewKafkaProducer()


# 편의 함수들
def send_user_event(event_type: str, user_id: str, data: Dict[str, Any]) -> bool:
    from flask import current_app

    topic = current_app.config.get('KAFKA_TOPIC_USER_EVENT', 'user-event')

    event_data = {
        'event_type': event_type,
        'user_id': user_id,
        'data': data,
        'timestamp': data.get('timestamp')  # ISO format string
    }

    return kafka_producer.send_event(topic, event_data, key=user_id)


def send_video_event(event_type: str, video_id: str, user_id: str, data: Dict[str, Any]) -> bool:
    from flask import current_app

    topic = current_app.config.get('KAFKA_TOPIC_VIDEO_EVENT', 'video-event')

    event_data = {
        'event_type': event_type,
        'video_id': video_id,
        'user_id': user_id,
        'data': data,
        'timestamp': data.get('timestamp')
    }

    return kafka_producer.send_event(topic, event_data, key=video_id)
