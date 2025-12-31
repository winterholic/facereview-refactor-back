from flask import request, current_app
from flask_socketio import emit
from common.extensions import socketio, mongo_client
from common.cache.watching_data_cache import WatchingDataCache
from common.tasks.watching_data_tasks import save_watching_data_task
from app.models.mongodb.video_timeline_emotion_count import VideoTimelineEmotionCountRepository
from common.utils.logging_utils import get_logger

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


@socketio.on('connect', namespace='/watching')
def handle_connect():
    logger.info(f"클라이언트 연결됨: {request.sid}")
    emit('connected', {'status': 'success', 'message': 'Connected to watching server'})


@socketio.on('init_watching', namespace='/watching')
def handle_init_watching(data):
    try:
        video_view_log_id = data.get('video_view_log_id')
        user_id = data.get('user_id')
        video_id = data.get('video_id')

        if not all([video_view_log_id, user_id, video_id]):
            emit('error', {'status': 'error', 'message': 'Missing required fields'})
            return

        watching_cache.init_watching_data(
            video_view_log_id=video_view_log_id,
            user_id=user_id,
            video_id=video_id
        )

        logger.info(f"시청 초기화 완료: {video_view_log_id}")
        emit('init_success', {'status': 'success', 'message': 'Watching initialized'})

    except Exception as e:
        logger.error(f"시청 초기화 중 오류 발생: {e}")
        emit('error', {'status': 'error', 'message': str(e)})


@socketio.on('watch_frame', namespace='/watching')
def handle_watch_frame(data):
    try:
        video_view_log_id = data.get('video_view_log_id')
        millisecond = data.get('millisecond')
        frame_data = data.get('frame_data')

        if not all([video_view_log_id, millisecond is not None, frame_data]):
            emit('error', {'status': 'error', 'message': 'Missing required fields'})
            return

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
            millisecond=millisecond,
            emotion_percentages=emotion_percentages,
            most_emotion=user_emotion['most_emotion']
        )

        average_emotion = _get_average_emotion_at_time(video_view_log_id, millisecond)

        response = {
            'millisecond': millisecond,
            'user_emotion': user_emotion,
            'average_emotion': average_emotion
        }

        emit('frame_analyzed', response)

    except Exception as e:
        logger.error(f"프레임 분석 중 오류 발생: {e}")
        emit('error', {'status': 'error', 'message': str(e)})


@socketio.on('disconnect', namespace='/watching')
def handle_disconnect():
    logger.info(f"클라이언트 연결 해제됨: {request.sid}")

    # 비동기로 데이터 저장 (사용자는 바로 응답 받음)
    # Thread를 사용하여 백그라운드에서 처리
    # 주의: Flask app context가 필요하므로 app을 전달
    # 실제로는 Celery 같은 task queue를 사용하는 것이 더 좋음
    # 여기서는 간단히 Thread로 구현

    # TODO: 실제 운영 환경에서는 Celery나 RQ 같은 task queue 사용 권장


@socketio.on('end_watching', namespace='/watching')
def handle_end_watching(data):
    try:
        video_view_log_id = data.get('video_view_log_id')
        client_info = data.get('client_info', {})

        if not video_view_log_id:
            emit('error', {'status': 'error', 'message': 'Missing video_view_log_id'})
            return

        #NOTE: Celery task를 비동기로 실행
        task = save_watching_data_task.delay(
            video_view_log_id=video_view_log_id,
            client_info=client_info
        )

        logger.info(f"시청 종료: {video_view_log_id} (Celery task ID: {task.id})")
        emit('end_success', {
            'status': 'success',
            'message': 'Watching data is being saved',
            'task_id': task.id
        })

    except Exception as e:
        logger.error(f"시청 종료 중 오류 발생: {e}")
        emit('error', {'status': 'error', 'message': str(e)})


def _get_average_emotion_at_time(video_view_log_id: str, millisecond: int) -> dict:
    try:
        cached_data = watching_cache.get_watching_data(video_view_log_id)
        if not cached_data:
            return _get_default_emotion()

        video_id = cached_data['video_id']

        mongo_db = mongo_client[current_app.config['MONGO_DB_NAME']]
        timeline_count_repo = VideoTimelineEmotionCountRepository(mongo_db)

        timeline_count = timeline_count_repo.find_by_video_id(video_id)

        if not timeline_count:
            return _get_default_emotion()

        emotion_percentages = timeline_count.get_emotion_percentages_at_time(millisecond)

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
