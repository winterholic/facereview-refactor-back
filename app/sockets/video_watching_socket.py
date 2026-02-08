from flask import request, current_app
from flask_socketio import emit
from common import extensions
from common.extensions import socketio, redis_client
from common.cache.watching_data_cache import WatchingDataCache
from common.tasks.watching_data_tasks import save_watching_data_task
from app.models.mongodb.video_timeline_emotion_count import VideoTimelineEmotionCountRepository
from app.models.mongodb.video_distribution import VideoDistributionRepository
from app.models.mongodb.youtube_watching_data import YoutubeWatchingDataRepository
from app.models.video_view_log import VideoViewLog
from app.models.video import Video
from common.extensions import db
from common.utils.logging_utils import get_logger
from common.utils.kafka_producer import send_watch_frame_event
import json

logger = get_logger('socket')

VIDEO_CATEGORY_TTL = 86400  # 24시간

DEDUPE_TTL_SECONDS = 3600  # 1시간

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

# NOTE : [DEPRECATED] watch_frame에서 자동 초기화하므로 호출 불필요
# NOTE : 하위 호환성을 위해 유지
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

# NOTE : frame_data 보내는 socket 이벤트 (init_watching 없이 단독으로 동작)
@socketio.on('watch_frame')
def handle_watch_frame(message):
    try:
        video_view_log_id = message.get('video_view_log_id')
        user_id = message.get('user_id')
        video_id = message.get('video_id')
        youtube_running_time = message.get('youtube_running_time')
        frame_data = message.get('frame_data')
        duration = message.get('duration')

        if not all([video_view_log_id, user_id, video_id, youtube_running_time is not None, frame_data]):
            return {
                'status': 'error',
                'message': 'Missing required fields'
            }

        #NOTE: 캐시 데이터가 없으면 초기화 (기존 init_watching 역할)
        cached_data = watching_cache.get_watching_data(video_view_log_id)
        if not cached_data:
            watching_cache.init_watching_data(
                video_view_log_id=video_view_log_id,
                user_id=user_id,
                video_id=video_id,
                duration=duration
            )
            #NOTE: Redis에 타임라인 평균 감정 데이터 미리 캐싱 (최초 1회)
            _cache_timeline_emotion_data(video_view_log_id, video_id)

            #NOTE: RDB video_view_log 테이블에 시청 기록 저장 (최초 1회)
            _create_video_view_log(video_view_log_id, user_id, video_id)

            logger.info(f"watch_frame에서 캐시 초기화 완료: {video_view_log_id}")

        #NOTE: 감정 분석
        user_emotion = get_emotion_analyzer().analyze_emotion(frame_data)

        emotion_percentages = {
            'happy': user_emotion['happy'],
            'neutral': user_emotion['neutral'],
            'surprise': user_emotion['surprise'],
            'sad': user_emotion['sad'],
            'angry': user_emotion['angry']
        }

        #NOTE: 캐시에 프레임 데이터 추가
        watching_cache.add_frame_data(
            video_view_log_id=video_view_log_id,
            youtube_running_time=youtube_running_time,
            emotion_percentages=emotion_percentages,
            most_emotion=user_emotion['most_emotion']
        )

        #NOTE: Kafka로 프레임 데이터 백업 전송
        send_watch_frame_event(
            video_view_log_id=video_view_log_id,
            user_id=user_id,
            video_id=video_id,
            youtube_running_time=youtube_running_time,
            emotion_percentages=emotion_percentages,
            most_emotion=user_emotion['most_emotion']
        )

        #NOTE: 평균 감정 데이터 조회 (현재 프레임 저장 전에 조회해야 내 데이터가 포함 안 됨)
        average_emotion = _get_average_emotion_at_time(video_view_log_id, youtube_running_time)

        #NOTE: 실시간 통계 업데이트 (MongoDB 3개 컬렉션 저장) - 평균 조회 후에 저장
        _update_realtime_statistics(
            video_view_log_id=video_view_log_id,
            user_id=user_id,
            video_id=video_id,
            youtube_running_time=youtube_running_time,
            emotion_percentages=emotion_percentages,
            most_emotion=user_emotion['most_emotion'],
            duration=duration
        )

        response = {
            'youtube_running_time': youtube_running_time,
            'user_emotion': user_emotion,
            'average_emotion': average_emotion
        }

        return {
            'status': 'success',
            'message': 'Frame analyzed',
            'response': response
        }

    except Exception as e:
        logger.error(f"프레임 분석 중 오류 발생: {e}", exc_info=True)
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


# NOTE : [OPTIONAL] youtube_watching_data 저장용 (개인 시청 기록)
# NOTE : 호출하지 않아도 실시간 통계는 watch_frame에서 저장됨
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


def _get_average_emotion_at_time(video_view_log_id: str, youtube_running_time: float) -> dict:
    try:
        cached_data = watching_cache.get_watching_data(video_view_log_id)
        if not cached_data:
            return _get_default_emotion()

        video_id = cached_data['video_id']

        #NOTE: 먼저 Redis에서 조회 (빠름)
        redis_emotion_data = _get_timeline_emotion_from_redis(video_view_log_id, youtube_running_time)

        if redis_emotion_data == "EMPTY":
            #NOTE: Redis 캐시는 있지만 해당 시간 데이터가 없음 → 기본값 반환 (MongoDB fallback 안 함)
            return _get_default_emotion()
        elif redis_emotion_data is not None:
            #NOTE: Redis에서 데이터 찾음
            return redis_emotion_data

        #NOTE: Redis 캐시 자체가 없을 때만 MongoDB fallback (세션 중간에 캐시가 만료된 경우 등)
        logger.debug(f"Redis 캐시 없음, MongoDB fallback: {video_view_log_id}")

        timeline_count_repo = VideoTimelineEmotionCountRepository(extensions.mongo_db)
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
        timeline_count_repo = VideoTimelineEmotionCountRepository(extensions.mongo_db)
        timeline_count = timeline_count_repo.find_by_video_id(video_id)

        timeline_data = {}

        if timeline_count and timeline_count.counts:
            #NOTE: 모든 타임라인 데이터를 딕셔너리로 변환
            for time_key, counts_data in timeline_count.counts.items():
                # NOTE: 객체 형태 {"neutral": 5, ...} 또는 배열 형태 [5, 3, ...] 둘 다 지원
                if isinstance(counts_data, dict):
                    total = sum(counts_data.values())
                    if total > 0:
                        emotion_percentages = {
                            label: round(counts_data.get(label, 0) / total, 3)
                            for label in timeline_count.emotion_labels
                        }
                else:
                    total = sum(counts_data)
                    if total > 0:
                        emotion_percentages = {
                            label: round(count / total, 3)
                            for label, count in zip(timeline_count.emotion_labels, counts_data)
                        }

                if total > 0:
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

        #NOTE: Redis에 저장 (데이터가 없어도 빈 객체 {} 캐싱 - MongoDB fallback 방지)
        #NOTE: TTL: 3시간 = 10800초
        if redis_client:
            redis_client.setex(
                redis_key,
                10800,  # 3시간
                json.dumps(timeline_data)  # 빈 객체 {}도 캐싱됨
            )
            logger.info(f"타임라인 데이터 Redis 캐싱 완료: {video_view_log_id} ({len(timeline_data)}개 타임스탬프)")

    except Exception as e:
        logger.error(f"타임라인 데이터 캐싱 중 오류 발생: {e}")


def _get_timeline_emotion_from_redis(video_view_log_id: str, youtube_running_time: float):
    """
    Redis에서 타임라인 감정 데이터 조회.
    Returns:
        - dict: 해당 시간의 감정 데이터
        - "EMPTY": Redis에 캐시는 있지만 해당 시간 데이터가 없음 (MongoDB fallback 하지 말 것)
        - None: Redis에 캐시 자체가 없음 (MongoDB fallback 필요)
    """
    try:
        redis_key = f"facereview:session:{video_view_log_id}:timeline"

        if not redis_client:
            return None

        #NOTE: Redis에서 타임라인 데이터 조회
        cached_data = redis_client.get(redis_key)
        if cached_data is None:
            return None  # 캐시 자체가 없음 → MongoDB fallback

        timeline_data = json.loads(cached_data)
        # NOTE: centisecond 단위로 변환 (20.29초 → "2029")
        time_key = str(int(float(youtube_running_time) * 100))

        result = timeline_data.get(time_key)
        if result:
            return result
        else:
            # NOTE: 캐시는 있지만 해당 시간 데이터가 없음 → MongoDB fallback 하지 않음
            return "EMPTY"

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


def _get_video_category(video_id: str) -> str:
    """
    비디오 카테고리를 Redis 캐시에서 조회하거나, 없으면 RDB에서 조회 후 캐싱.
    recommendation_scores 계산에 사용됨.
    """
    try:
        redis_key = f"facereview:video:{video_id}:category"

        # NOTE: Redis에서 먼저 조회
        if redis_client:
            cached_category = redis_client.get(redis_key)
            if cached_category:
                return cached_category.decode('utf-8') if isinstance(cached_category, bytes) else cached_category

        # NOTE: RDB에서 조회
        video = Video.query.filter_by(video_id=video_id).first()
        if not video:
            logger.warning(f"Video not found: {video_id}")
            return 'etc'

        # NOTE: GenreEnum을 문자열로 변환
        category = video.category.value if video.category else 'etc'

        # NOTE: Redis에 캐싱 (24시간 TTL)
        if redis_client:
            redis_client.setex(redis_key, VIDEO_CATEGORY_TTL, category)
            logger.debug(f"Video category cached: {video_id} -> {category}")

        return category

    except Exception as e:
        logger.error(f"비디오 카테고리 조회 중 오류 발생: {e}")
        return 'etc'


def _check_dedupe(video_view_log_id: str, youtube_running_time: int) -> bool:
    """
    동일 세션에서 같은 초(second)에 대해 중복 집계를 방지합니다.
    Redis SETNX를 사용하여 이미 집계된 경우 False를 반환합니다.
    """
    try:
        if not redis_client:
            return True  # Redis가 없으면 항상 집계 허용

        dedupe_key = f"facereview:dedupe:{video_view_log_id}:{youtube_running_time}"

        # SETNX: 키가 없으면 설정하고 True 반환, 이미 있으면 False 반환
        result = redis_client.setnx(dedupe_key, 1)

        if result:
            # TTL 설정 (1시간)
            redis_client.expire(dedupe_key, DEDUPE_TTL_SECONDS)
            return True

        return False

    except Exception as e:
        logger.error(f"중복 체크 중 오류 발생: {e}")
        return True  # 에러 시 집계 허용 (데이터 손실 방지)


def _update_realtime_statistics(
    video_view_log_id: str,
    user_id: str,
    video_id: str,
    youtube_running_time: float,
    emotion_percentages: dict,
    most_emotion: str,
    duration: int = None
):
    """
    watch_frame 이벤트에서 실시간으로 3개 컬렉션을 업데이트합니다.
    - youtube_watching_data: 개인 시청 기록 (프레임별 타임라인)
    - video_timeline_emotion_count: 해당 초의 감정 카운트 증가
    - video_distribution: 해당 영상의 전체 감정 카운트 증가
    """
    try:
        if extensions.mongo_db is None:
            logger.error("[SAVE] extensions.mongo_db is None!")
            return

        # NOTE: youtube_running_time 타입 확인 및 변환
        running_time = float(youtube_running_time) if youtube_running_time is not None else 0.0
        time_key_preview = str(int(running_time * 100))

        logger.info(f"[REALTIME_SAVE] video_id={video_id}, original_time={youtube_running_time} (type={type(youtube_running_time).__name__}), time_key={time_key_preview}, emotion={most_emotion}")

        # 1. youtube_watching_data 업데이트 (개인 시청 기록)
        watching_data_repo = YoutubeWatchingDataRepository(extensions.mongo_db)
        watching_data_repo.upsert_frame(
            video_view_log_id=video_view_log_id,
            user_id=user_id,
            video_id=video_id,
            youtube_running_time=running_time,
            emotion_percentages=emotion_percentages,
            most_emotion=most_emotion,
            duration=duration
        )

        # 2. video_timeline_emotion_count 업데이트
        timeline_count_repo = VideoTimelineEmotionCountRepository(extensions.mongo_db)
        timeline_count_repo.increment_emotion(
            video_id=video_id,
            youtube_running_time=running_time,
            emotion=most_emotion
        )

        # 3. video_distribution 업데이트 (카테고리 기반 recommendation_scores 계산 포함)
        category = _get_video_category(video_id)
        video_dist_repo = VideoDistributionRepository(extensions.mongo_db)
        video_dist_repo.increment_emotion(
            video_id=video_id,
            emotion=most_emotion,
            category=category
        )

        logger.info(f"[REALTIME_SAVE] 완료: {video_view_log_id}, time_key={time_key_preview}, emotion={most_emotion}, category={category}")

    except Exception as e:
        logger.error(f"실시간 통계 업데이트 중 오류 발생: {e}", exc_info=True)


def _create_video_view_log(video_view_log_id: str, user_id: str, video_id: str):
    """
    RDB video_view_log 테이블에 시청 기록을 저장합니다.
    watch_frame 최초 호출 시 1회만 실행됩니다.
    """
    try:
        # 이미 존재하는지 확인
        existing = VideoViewLog.query.filter_by(video_view_log_id=video_view_log_id).first()
        if existing:
            logger.debug(f"video_view_log 이미 존재: {video_view_log_id}")
            return

        video_view_log = VideoViewLog(
            video_view_log_id=video_view_log_id,
            user_id=user_id,
            video_id=video_id
        )
        db.session.add(video_view_log)
        db.session.commit()
        logger.info(f"video_view_log 저장 완료: {video_view_log_id}")

    except Exception as e:
        db.session.rollback()
        logger.error(f"video_view_log 저장 중 오류 발생: {e}", exc_info=True)
