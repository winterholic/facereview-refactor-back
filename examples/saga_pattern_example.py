"""
사가 패턴 사용 예제

이 파일은 사가 패턴을 사용하여 RDB + MongoDB 통합 트랜잭션을 처리하는 예제입니다.
"""

from datetime import datetime
from common.decorator.db_decorators import union_transactional
from common.extensions import db, mongo_db
from app.models import Video
from app.models.mongodb.video_distribution import (
    VideoDistribution,
    VideoDistributionRepository,
    EmotionAverages,
    RecommendationScores
)
from app.models.mongodb.youtube_watching_data import (
    YoutubeWatchingData,
    YoutubeWatchingDataRepository,
    EmotionPercentages,
    ClientInfo
)


# ========================================
# 예제 1: 기본 사용법 - 성공 케이스
# ========================================

@union_transactional
def example_1_success():
    """
    영상 생성 + MongoDB 데이터 저장 (성공)

    실행:
        video = example_1_success()
        print(f"영상 생성 성공: {video.id}")
    """

    # 1. RDB - 영상 생성
    video = Video(
        title="사가 패턴 테스트 영상",
        thumbnail_url="https://example.com/thumb.jpg",
        video_url="https://example.com/video.mp4",
        duration=300,
        is_active=True
    )
    db.session.add(video)
    db.session.flush()  # ⚠️ ID 생성을 위해 flush() 필수

    print(f"[1단계] Video 생성: {video.id}")

    # 2. MongoDB - 시청 데이터 저장
    watching_repo = YoutubeWatchingDataRepository(mongo_db)
    watching = YoutubeWatchingData(
        user_id="user_123",
        video_id=str(video.id),
        video_view_log_id=f"log_{video.id}_123",
        created_at=datetime.utcnow(),
        completion_rate=0.85,
        dominant_emotion='happy',
        emotion_percentages=EmotionPercentages(
            neutral=0.1,
            happy=0.6,
            surprise=0.2,
            sad=0.05,
            angry=0.05
        ),
        client_info=ClientInfo(
            ip_address="127.0.0.1",
            user_agent="Mozilla/5.0",
            is_mobile=False
        )
    )
    watching_repo.insert(watching)

    print(f"[2단계] YoutubeWatchingData 생성: {watching.video_view_log_id}")

    # 3. MongoDB - 통계 데이터 저장
    dist_repo = VideoDistributionRepository(mongo_db)
    distribution = VideoDistribution(
        video_id=str(video.id),
        average_completion_rate=0.85,
        emotion_averages=EmotionAverages(
            neutral=0.1,
            happy=0.6,
            surprise=0.2,
            sad=0.05,
            angry=0.05
        ),
        recommendation_scores=RecommendationScores(
            neutral=5.0,
            happy=30.0,
            surprise=10.0,
            sad=2.5,
            angry=2.5
        ),
        dominant_emotion='happy'
    )
    dist_repo.upsert(distribution)

    print(f"[3단계] VideoDistribution 생성: {distribution.video_id}")
    print("[성공] 모든 단계 완료!")

    return video


# ========================================
# 예제 2: 실패 케이스 - 자동 롤백
# ========================================

@union_transactional
def example_2_failure():
    """
    영상 생성 + MongoDB 데이터 저장 (실패 - 보상 트랜잭션 실행)

    실행:
        try:
            example_2_failure()
        except Exception as e:
            print(f"예상된 에러 발생: {e}")
            # RDB 롤백 + MongoDB 보상 완료
    """

    # 1. RDB - 영상 생성
    video = Video(
        title="실패 테스트 영상",
        thumbnail_url="https://example.com/thumb.jpg",
        video_url="https://example.com/video.mp4",
        duration=300,
        is_active=True
    )
    db.session.add(video)
    db.session.flush()

    print(f"[1단계] Video 생성: {video.id}")

    # 2. MongoDB - 시청 데이터 저장
    watching_repo = YoutubeWatchingDataRepository(mongo_db)
    watching = YoutubeWatchingData(
        user_id="user_456",
        video_id=str(video.id),
        video_view_log_id=f"log_{video.id}_456",
        created_at=datetime.utcnow(),
        completion_rate=0.5,
        dominant_emotion='neutral'
    )
    watching_repo.insert(watching)

    print(f"[2단계] YoutubeWatchingData 생성: {watching.video_view_log_id}")

    # 3. 의도적 에러 발생
    print("[3단계] 의도적 에러 발생...")
    raise ValueError("테스트를 위한 의도적 에러!")

    # ❌ 여기까지 도달하지 못함
    # ✅ 자동 롤백:
    #    - RDB: Video 롤백
    #    - MongoDB: YoutubeWatchingData 자동 삭제 (보상)


# ========================================
# 예제 3: 업데이트 + 보상
# ========================================

@union_transactional
def example_3_update_and_compensate(video_id: str):
    """
    기존 영상 통계 업데이트 + 실패 시 이전 값으로 복원

    실행:
        # 성공 케이스
        example_3_update_and_compensate("existing_video_id")

        # 실패 케이스 (보상 발생)
        try:
            example_3_update_and_compensate("existing_video_id")
        except Exception as e:
            print("이전 값으로 복원됨")
    """

    dist_repo = VideoDistributionRepository(mongo_db)

    # 1. 기존 데이터 조회
    existing = dist_repo.find_by_video_id(video_id)
    if not existing:
        raise ValueError(f"영상을 찾을 수 없습니다: {video_id}")

    print(f"[이전 값] 평균 완료율: {existing.average_completion_rate}")

    # 2. 업데이트
    updated = VideoDistribution(
        video_id=video_id,
        average_completion_rate=0.95,  # 업데이트된 값
        emotion_averages=existing.emotion_averages,
        recommendation_scores=existing.recommendation_scores,
        dominant_emotion='happy'
    )
    compensation_data = dist_repo.upsert(updated)

    print(f"[업데이트] 평균 완료율: 0.95")
    print(f"[보상 데이터] {compensation_data}")

    # 3. 의도적 에러 발생 (테스트용 - 주석 해제하여 보상 테스트)
    # raise ValueError("업데이트 후 에러!")

    # ✅ 성공: 업데이트된 값 유지
    # ❌ 실패: 이전 값으로 자동 복원 (보상)

    return updated


# ========================================
# 예제 4: 복잡한 트랜잭션
# ========================================

@union_transactional
def example_4_complex_transaction():
    """
    복잡한 비즈니스 로직 - 여러 MongoDB 컬렉션 동시 작업

    실행:
        result = example_4_complex_transaction()
        print(f"생성된 영상들: {result}")
    """

    videos = []

    # 1. 여러 영상 생성
    for i in range(3):
        video = Video(
            title=f"복잡한 트랜잭션 테스트 영상 {i+1}",
            thumbnail_url=f"https://example.com/thumb_{i}.jpg",
            video_url=f"https://example.com/video_{i}.mp4",
            duration=300 + i * 60,
            is_active=True
        )
        db.session.add(video)
        db.session.flush()
        videos.append(video)

        print(f"[{i+1}단계] Video 생성: {video.id}")

        # 2. 각 영상에 대한 MongoDB 데이터 생성
        watching_repo = YoutubeWatchingDataRepository(mongo_db)
        watching = YoutubeWatchingData(
            user_id=f"user_{i}",
            video_id=str(video.id),
            video_view_log_id=f"log_{video.id}_{i}",
            created_at=datetime.utcnow(),
            completion_rate=0.7 + i * 0.1,
            dominant_emotion='neutral'
        )
        watching_repo.insert(watching)

        dist_repo = VideoDistributionRepository(mongo_db)
        distribution = VideoDistribution(
            video_id=str(video.id),
            average_completion_rate=0.7 + i * 0.1,
            dominant_emotion='neutral'
        )
        dist_repo.upsert(distribution)

    print(f"[성공] {len(videos)}개 영상 및 관련 데이터 생성 완료!")

    # ✅ 성공: 모든 영상 및 데이터 생성
    # ❌ 실패: 모든 영상 및 MongoDB 데이터 자동 롤백

    return videos


# ========================================
# 실행 예제
# ========================================

if __name__ == "__main__":
    """
    Flask 애플리케이션 컨텍스트 내에서 실행해야 합니다.

    실행 방법:
        from app import create_app
        app = create_app()

        with app.app_context():
            # 예제 1: 성공 케이스
            video = example_1_success()
            print(f"생성된 영상 ID: {video.id}")

            # 예제 2: 실패 케이스
            try:
                example_2_failure()
            except Exception as e:
                print(f"예상된 에러: {e}")

            # 예제 3: 업데이트
            example_3_update_and_compensate(str(video.id))

            # 예제 4: 복잡한 트랜잭션
            videos = example_4_complex_transaction()
    """
    print("이 파일은 Flask 애플리케이션 컨텍스트 내에서 실행해야 합니다.")
    print("위의 주석을 참고하여 실행하세요.")
