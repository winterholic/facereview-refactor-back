"""
Kafka Consumer Runner
Kafka 이벤트를 소비하는 별도 프로세스

실행 방법:
    python run_kafka_consumer.py
"""

import os
import sys
import logging
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Kafka Consumer 실행"""

    # Kafka 설정 가져오기
    bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    group_id = os.getenv('KAFKA_GROUP_ID', 'facereview-consumer')

    logger.info("=" * 50)
    logger.info("Kafka Consumer Starting...")
    logger.info(f"Bootstrap Servers: {bootstrap_servers}")
    logger.info(f"Group ID: {group_id}")
    logger.info("=" * 50)

    # Consumer 생성 및 초기화
    from common.utils.kafka_consumer import (
        FacereviewKafkaConsumer,
        handle_user_event,
        handle_watch_frame_event
    )

    #NOTE: 여러 토픽을 구독하는 통합 Consumer
    topics = ['user-event', 'watch-frame-event']
    consumer = FacereviewKafkaConsumer(
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        topics=topics
    )

    if not consumer.initialize():
        logger.error("Failed to initialize Kafka Consumer")
        sys.exit(1)

    #NOTE: 토픽에 따라 다른 핸들러 호출
    def unified_handler(topic: str, event_data: dict):
        if topic == 'user-event':
            handle_user_event(topic, event_data)
        elif topic == 'watch-frame-event':
            handle_watch_frame_event(topic, event_data)
        else:
            logger.warning(f"Unknown topic: {topic}")

    try:
        logger.info(f"Kafka Consumer is ready. Subscribed topics: {topics}")
        logger.info("Waiting for messages...")
        consumer.consume(unified_handler)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down...")
        consumer.stop()
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        consumer.close()
        sys.exit(1)


if __name__ == '__main__':
    main()
