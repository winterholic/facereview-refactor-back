from flask import request, current_app
from flask_socketio import emit
from common.extensions import socketio, redis_client, mongo_db
from common.cache.watching_data_cache import WatchingDataCache
from common.tasks.watching_data_tasks import save_watching_data_task
from app.models.mongodb.video_timeline_emotion_count import VideoTimelineEmotionCountRepository
from common.utils.logging_utils import get_logger
from common.utils.kafka_producer import send_watch_frame_event
import json

logger = get_logger('socket')

#NOTE: Lazy loading을 위한 전역 변수
_emotion_analyzer = None

#NOTE: WatchingDataCache 싱글톤 인스턴스
watching_cache = WatchingDataCache()


def get_emotion_analyzer():
    global _emotion_analyzer
    if _emotion_analyzer is None:
        from common.ml.emotion_analyzer import EmotionAnalyzer
        _emotion_analyzer = EmotionAnalyzer()
        logger.info("EmotionAnalyzer 로드 완료 (Lazy loading 적용)")
    return _emotion_analyzer


# NOTE : socket 연결 테스트용 이벤트(단순 테스트용)
@socketio.on('connect')
def handle_connect(message):
    logger.info(f"클라이언트 연결됨: {request.sid}")

    # NOTE : emit 대신 return 사용
    # emit('connected', {'status': 'success', 'message': '서버에 연결되었습니다.'})
    return {
        'sid': request.sid,
        'status': 'success',
        'message': '서버에 연결완료 되었습니다.'
    }

# NOTE : 소켓 연결 전 테스트용 socket 이벤트(처음에 페이지 진입하면 한번 쏴보는 용도)
@socketio.on('init_watching')
def handle_init_watching(message):
    try:
        video_view_log_id = message.get('video_view_log_id')
        user_id = message.get('user_id')
        video_id = message.get('video_id')
        duration = message.get('duration')

        if not all([video_view_log_id, user_id, video_id, duration]):

            # NOTE : emit 대신 return 사용
            # emit('error', {'status': 'error', 'message': 'Missing required fields'})

            return {
                'status': 'error',
                'message': 'Missing required fields'
            }

        watching_cache.init_watching_data(
            video_view_log_id=video_view_log_id,
            user_id=user_id,
            video_id=video_id,
            duration=duration
        )

        #NOTE: Redis에 타임라인 평균 감정 데이터 미리 캐싱 (3시간 TTL)
        _cache_timeline_emotion_data(video_view_log_id, video_id)

        logger.info(f"시청 초기화 완료: {video_view_log_id}")

        # NOTE : emit 대신 return 사용
        # emit('init_success', {'status': 'success', 'message': 'Watching initialized'})

        return {
            'status': 'success',
            'message': 'Watching initialized'
        }

    except Exception as e:
        logger.error(f"시청 초기화 중 오류 발생: {e}")

        # NOTE : emit 대신 return 사용
        # emit('error', {'status': 'error', 'message': str(e)})
        return {
            'status': 'error',
            'message': str(e)
        }

# NOTE : frame_data 보내는 socket 이벤트
@socketio.on('watch_frame')
def handle_watch_frame(message):
    try:
        video_view_log_id = message.get('video_view_log_id')
        youtube_running_time = message.get('youtube_running_time')
        frame_data = message.get('frame_data')
        duration = message.get('duration')

        if not all([video_view_log_id, youtube_running_time, duration is not None, frame_data]):

            # NOTE : emit 대신 return 사용
            # emit('error', {'status': 'error', 'message': 'Missing required fields'})

            return {
                'status': 'error',
                'message': 'Missing required fields'
            }

        user_emotion = get_emotion_analyzer().analyze_emotion(frame_data)

        emotion_percentages = {
            'happy': user_emotion['happy'],
            'neutral': user_emotion['neutral'],
            'surprise': user_emotion['surprise'],
            'sad': user_emotion['sad'],
            'angry': user_emotion['angry']
        }

        watching_cache.add_frame_data(
            video_view_log_id=video_view_log_id,
            youtube_running_time=youtube_running_time,
            emotion_percentages=emotion_percentages,
            most_emotion=user_emotion['most_emotion']
        )

        #NOTE: Kafka로 프레임 데이터 백업 전송 (비동기)
        cached_data = watching_cache.get_watching_data(video_view_log_id)
        if cached_data:
            send_watch_frame_event(
                video_view_log_id=video_view_log_id,
                user_id=cached_data['user_id'],
                video_id=cached_data['video_id'],
                youtube_running_time=youtube_running_time,
                emotion_percentages=emotion_percentages,
                most_emotion=user_emotion['most_emotion']
            )

        average_emotion = _get_average_emotion_at_time(video_view_log_id, youtube_running_time)

        response = {
            'youtube_running_time': youtube_running_time,
            'user_emotion': user_emotion,
            'average_emotion': average_emotion
        }

        # NOTE : emit 대신 return 사용
        # emit('frame_analyzed', response)

        return {
            'status': 'success',
            'message': 'Frame analyzed',
            'response': response
        }

    except Exception as e:
        logger.error(f"프레임 분석 중 오류 발생: {e}")

        # NOTE : emit 대신 return 사용
        # emit('error', {'status': 'error', 'message': str(e)})

        return {
            'status': 'error',
            'message': str(e)
        }


# NOTE : 그냥 disconnect 테스트용 socket 이벤트
@socketio.on('disconnect')
def handle_disconnect(message):
    logger.info(f"클라이언트 연결 해제됨: {request.sid}")
    # NOTE : emit 대신 return 사용
    return {
        'sid': request.sid,
        'status': 'success',
        'message': '서버 연결이 종료 되었습니다.'
    }


# NOTE : emit 대신 return 사용
@socketio.on('end_watching')
def handle_end_watching(message):
    try:
        video_view_log_id = message.get('video_view_log_id')
        duration = message.get('duration')
        client_info = message.get('client_info', {})

        if not video_view_log_id:
            return {
                'status': 'error',
                'message': 'Missing video_view_log_id'
            }

        #NOTE: Celery Worker는 별도 프로세스이므로 캐시 데이터를 직접 전달
        cached_data = watching_cache.remove_watching_data(video_view_log_id)
        if not cached_data:
            logger.warning(f"No cached data for {video_view_log_id}")
            return {
                'status': 'error',
                'message': 'No watching data found'
            }

        #NOTE: Celery JSON serializer는 datetime 처리 불가 → 제거 (서비스에서 새로 생성)
        cached_data.pop('created_at', None)

        task = save_watching_data_task.delay(
            video_view_log_id=video_view_log_id,
            duration=duration,
            client_info=client_info,
            cached_data=cached_data
        )

        #NOTE: 시청 종료 시 Redis 타임라인 캐시 삭제 (세션 종료)
        _delete_timeline_cache(video_view_log_id)

        logger.info(f"시청 종료: {video_view_log_id} (Celery task ID: {task.id})")
        # NOTE : emit 대신 return 사용
        # emit('end_success', {
        #     'status': 'success',
        #     'message': 'Watching data is being saved'
        # })

        return {
            'status': 'success',
            'message': 'Watching data is being saved'
        }

    except Exception as e:
        logger.error(f"시청 종료 중 오류 발생: {e}")

        # NOTE : emit 대신 return 사용
        # emit('error', {'status': 'error', 'message': str(e)})

        return {
            'status': 'error',
            'message': str(e)
        }


def _get_average_emotion_at_time(video_view_log_id: str, youtube_running_time: int) -> dict:
    try:
        cached_data = watching_cache.get_watching_data(video_view_log_id)
        if not cached_data:
            return _get_default_emotion()

        video_id = cached_data['video_id']

        #NOTE: 먼저 Redis에서 조회 (빠름)
        redis_emotion_data = _get_timeline_emotion_from_redis(video_view_log_id, youtube_running_time)
        if redis_emotion_data:
            return redis_emotion_data

        #NOTE: Redis에 없으면 MongoDB 조회 (fallback)
        timeline_count_repo = VideoTimelineEmotionCountRepository(mongo_db)

        timeline_count = timeline_count_repo.find_by_video_id(video_id)

        if not timeline_count:
            return _get_default_emotion()

        emotion_percentages = timeline_count.get_emotion_percentages_at_time(youtube_running_time)

        if not emotion_percentages:
            return _get_default_emotion()

        emotion_data = {
            'neutral': round(emotion_percentages['neutral'] * 100, 2),
            'happy': round(emotion_percentages['happy'] * 100, 2),
            'surprise': round(emotion_percentages['surprise'] * 100, 2),
            'sad': round(emotion_percentages['sad'] * 100, 2),
            'angry': round(emotion_percentages['angry'] * 100, 2)
        }

        most_emotion = max(emotion_data, key=emotion_data.get)
        emotion_data['most_emotion'] = most_emotion

        return emotion_data

    except Exception as e:
        logger.error(f"평균 감정 데이터 조회 중 오류 발생: {e}")
        return _get_default_emotion()


def _get_default_emotion() -> dict:
    return {
        'neutral': 100.0,
        'happy': 0.0,
        'surprise': 0.0,
        'sad': 0.0,
        'angry': 0.0,
        'most_emotion': 'neutral'
    }


def _cache_timeline_emotion_data(video_view_log_id: str, video_id: str):
    try:
        redis_key = f"facereview:session:{video_view_log_id}:timeline"

        #NOTE: 이미 Redis에 캐싱되어 있으면 스킵
        if redis_client and redis_client.exists(redis_key):
            logger.debug(f"타임라인 데이터가 이미 Redis에 캐싱되어 있음: {video_view_log_id}")
            return

        #NOTE: MongoDB에서 타임라인 데이터 조회
        timeline_count_repo = VideoTimelineEmotionCountRepository(mongo_db)
        timeline_count = timeline_count_repo.find_by_video_id(video_id)

        if not timeline_count:
            logger.debug(f"타임라인 데이터 없음: {video_id}")
            return

        #NOTE: 모든 타임라인 데이터를 딕셔너리로 변환
        timeline_data = {}
        for time_key, counts in timeline_count.counts.items():
            total = sum(counts)
            if total > 0:
                emotion_percentages = {
                    label: round(count / total, 3)
                    for label, count in zip(timeline_count.emotion_labels, counts)
                }

                emotion_data = {
                    'neutral': round(emotion_percentages['neutral'] * 100, 2),
                    'happy': round(emotion_percentages['happy'] * 100, 2),
                    'surprise': round(emotion_percentages['surprise'] * 100, 2),
                    'sad': round(emotion_percentages['sad'] * 100, 2),
                    'angry': round(emotion_percentages['angry'] * 100, 2)
                }

                most_emotion = max(emotion_data, key=emotion_data.get)
                emotion_data['most_emotion'] = most_emotion

                timeline_data[time_key] = emotion_data

        #NOTE: Redis에 저장 (TTL: 3시간 = 10800초)
        if redis_client and timeline_data:
            redis_client.setex(
                redis_key,
                10800,  # 3시간
                json.dumps(timeline_data)
            )
            logger.info(f"타임라인 데이터 Redis 캐싱 완료: {video_view_log_id} ({len(timeline_data)}개 타임스탬프)")

    except Exception as e:
        logger.error(f"타임라인 데이터 캐싱 중 오류 발생: {e}")


def _get_timeline_emotion_from_redis(video_view_log_id: str, youtube_running_time: int) -> dict:
    try:
        redis_key = f"facereview:session:{video_view_log_id}:timeline"

        if not redis_client:
            return None

        #NOTE: Redis에서 타임라인 데이터 조회
        cached_data = redis_client.get(redis_key)
        if not cached_data:
            return None

        timeline_data = json.loads(cached_data)
        time_key = str(youtube_running_time)

        return timeline_data.get(time_key)

    except Exception as e:
        logger.error(f"Redis 타임라인 조회 중 오류 발생: {e}")
        return None


def _delete_timeline_cache(video_view_log_id: str):
    try:
        redis_key = f"facereview:session:{video_view_log_id}:timeline"

        if redis_client:
            redis_client.delete(redis_key)
            logger.debug(f"Redis 타임라인 캐시 삭제: {video_view_log_id}")

    except Exception as e:
        logger.error(f"Redis 캐시 삭제 중 오류 발생: {e}")
