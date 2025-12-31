from typing import List, Dict
from flask import current_app
from sqlalchemy import desc
import traceback


from common.extensions import db, mongo_db
from common.decorator.db_decorators import transactional, transactional_readonly
from common.exception.exceptions import BusinessError
from common.enum.error_code import APIError
from app.models.video import Video
from app.models.comment import Comment
from app.models.video_like import VideoLike
from app.models.user import User
from app.models.mongodb.video_distribution import VideoDistributionRepository
from app.models.mongodb.video_timeline_emotion_count import VideoTimelineEmotionCountRepository
from app.dto.watch import (
    VideoDetailDto, TimelineDataDto, TimelinePointDto,
    RecommendedVideoDto, RecommendedVideoListDto,
    CommentDto, CommentListDto,
    AddCommentResponseDto, UpdateCommentResponseDto,
    DeleteCommentResponseDto, ToggleLikeResponseDto
)


class WatchService:
    @staticmethod
    @transactional
    def get_video_detail(video_id: str, user_id: str = None) -> VideoDetailDto:
        video = db.session.query(Video).filter_by(video_id=video_id, is_deleted=0).first()
        if not video:
            raise BusinessError(APIError.VIDEO_NOT_FOUND)

        user_is_liked = False
        if user_id:
            like = db.session.query(VideoLike).filter_by(
                video_id=video_id,
                user_id=user_id
            ).first()
            user_is_liked = (like is not None)

        like_count = db.session.query(VideoLike).filter_by(video_id=video_id).count()
        comment_count = db.session.query(Comment).filter_by(video_id=video_id, is_deleted=0).count()

        timeline_data = WatchService._get_compressed_timeline_data(video_id, video.duration)

        video_detail_dto = VideoDetailDto(
            video_id=video.video_id,
            youtube_url=video.youtube_url,
            title=video.title,
            channel_name=video.channel_name or '',
            category=video.category.value,
            duration=video.duration,
            view_count=video.view_count,
            like_count=like_count,
            comment_count=comment_count,
            user_is_liked=user_is_liked,
            timeline_data=timeline_data
        )

        video.view_count += 1
        db.session.flush()

        return video_detail_dto

    @staticmethod
    def _get_compressed_timeline_data(video_id: str, duration: int) -> TimelineDataDto:
        timeline_repo = VideoTimelineEmotionCountRepository(mongo_db)

        timeline_count = timeline_repo.find_by_video_id(video_id)

        if not timeline_count:
            return WatchService._get_default_timeline_data()

        #NOTE: 밀리초 단위 리스트 생성 (0.1초 간격)
        duration_ms = duration * 1000
        milliseconds = list(range(0, duration_ms, 100))

        emotion_lists = {
            'happy': [],
            'neutral': [],
            'surprise': [],
            'sad': [],
            'angry': []
        }

        for ms in milliseconds:
            percentages = timeline_count.get_emotion_percentages_at_time(ms)

            if percentages:
                for emotion in ['happy', 'neutral', 'surprise', 'sad', 'angry']:
                    emotion_lists[emotion].append(percentages[emotion] * 100)
            else:
                for emotion in ['happy', 'neutral', 'surprise', 'sad', 'angry']:
                    emotion_lists[emotion].append(0.0)

        #NOTE: 100개 이상이면 압축 (최대한 100개 정도의 데이터 포인트로 압축)
        data_count = len(milliseconds)
        if data_count > 100:
            compressed_lists = {}
            max_points = 100
            parameter = max(1, round(data_count / max_points))

            for emotion, values in emotion_lists.items():
                compressed = []
                temp_sum = 0
                temp_count = 0
                temp_index = 1

                for idx, value in enumerate(values):
                    temp_sum += value
                    temp_count += 1

                    if temp_count == parameter or idx == len(values) - 1:
                        temp_avg = round(temp_sum / temp_count, 1)
                        compressed.append(TimelinePointDto(x=temp_index, y=temp_avg))
                        temp_sum = 0
                        temp_count = 0
                        temp_index += 1

                compressed_lists[emotion] = compressed
        else:
            compressed_lists = {}
            for emotion, values in emotion_lists.items():
                compressed_lists[emotion] = [
                    TimelinePointDto(x=idx + 1, y=round(val, 1))
                    for idx, val in enumerate(values)
                ]

        return TimelineDataDto(
            happy=compressed_lists['happy'],
            neutral=compressed_lists['neutral'],
            surprise=compressed_lists['surprise'],
            sad=compressed_lists['sad'],
            angry=compressed_lists['angry']
        )

    @staticmethod
    def _get_default_timeline_data() -> TimelineDataDto:
        default_point = [TimelinePointDto(x=1, y=0.0)]
        return TimelineDataDto(
            happy=default_point,
            neutral=default_point,
            surprise=default_point,
            sad=default_point,
            angry=default_point
        )

    @staticmethod
    @transactional_readonly
    def get_recommended_videos(video_id: str, page: int = 1, size: int = 10) -> RecommendedVideoListDto:
        current_video = db.session.query(Video).filter_by(video_id=video_id, is_deleted=0).first()
        if not current_video:
            raise BusinessError(APIError.VIDEO_NOT_FOUND)

        distribution_repo = VideoDistributionRepository(mongo_db)

        current_distribution = distribution_repo.find_by_video_id(video_id)
        if (not current_distribution) or (current_distribution.dominant_emotion is None):
            return RecommendedVideoListDto(
                videos=[],
                total=0,
                page=page,
                size=size,
                has_next=False
            )

        current_emotion = current_distribution.dominant_emotion
        current_category = current_video.category

        same_category_videos = db.session.query(Video.video_id, Video.youtube_url, Video.title).filter(
            Video.is_deleted == 0,
            Video.category == current_category,
            Video.video_id != video_id
        ).all()

        if not same_category_videos:
            return RecommendedVideoListDto(
                videos=[],
                total=0,
                page=page,
                size=size,
                has_next=False
            )

        video_id_list = [v.video_id for v in same_category_videos]
        video_info_dict = {
            v.video_id: {'youtube_url': v.youtube_url, 'title': v.title}
            for v in same_category_videos
        }

        mongo_query = {
            'video_id': {'$in': video_id_list},
            'dominant_emotion': current_emotion
        }

        video_distributions = distribution_repo.collection.find(mongo_query)

        scored_videos = []
        for dist_doc in video_distributions:
            vid = dist_doc['video_id']

            if vid not in video_info_dict:
                continue

            rec_scores = dist_doc.get('recommendation_scores', {})
            emotion_score = rec_scores.get(current_emotion, 0.0)

            emotion_averages = dist_doc.get('emotion_averages', {})
            emotion_per = emotion_averages.get(current_emotion, 0.0) * 100.0

            scored_videos.append({
                'video_id': vid,
                'youtube_url': video_info_dict[vid]['youtube_url'],
                'title': video_info_dict[vid]['title'],
                'dominant_emotion': current_emotion,
                'dominant_emotion_per': round(emotion_per, 2),
                'score': emotion_score
            })

        scored_videos.sort(key=lambda x: x['score'], reverse=True)

        total = len(scored_videos)
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        paginated_videos = scored_videos[start_idx:end_idx]

        video_dtos = [
            RecommendedVideoDto(
                video_id=v['video_id'],
                youtube_url=v['youtube_url'],
                title=v['title'],
                dominant_emotion=v['dominant_emotion'],
                dominant_emotion_per=v['dominant_emotion_per']
            )
            for v in paginated_videos
        ]

        return RecommendedVideoListDto(
            videos=video_dtos,
            total=total,
            page=page,
            size=size,
            has_next=(end_idx < total)
        )

    @staticmethod
    @transactional_readonly
    def get_comment_list(video_id: str, user_id: str = None) -> CommentListDto:
        video = db.session.query(Video).filter_by(video_id=video_id, is_deleted=0).first()
        if not video:
            raise BusinessError(APIError.VIDEO_NOT_FOUND)

        comments = db.session.query(Comment).join(User).filter(
            Comment.video_id == video_id,
            Comment.is_deleted == 0
        ).order_by(desc(Comment.created_at)).all()

        comment_dtos = []
        for comment in comments:
            is_mine = False
            if user_id:
                is_mine = (user_id == comment.user_id)

            comment_dtos.append(CommentDto(
                comment_id=comment.comment_id,
                user_id=comment.user_id,
                user_name=comment.user.name,
                user_profile_image_id=comment.user.profile_image_id,
                content=comment.content,
                is_modified=bool(comment.is_modified),
                created_at=comment.created_at.isoformat(),
                is_mine=is_mine
            ))

        return CommentListDto(
            comments=comment_dtos,
            total=len(comment_dtos)
        )

    @staticmethod
    @transactional
    def add_comment(video_id: str, user_id: str, content: str) -> AddCommentResponseDto:
        video = db.session.query(Video).filter_by(video_id=video_id, is_deleted=0).first()
        if not video:
            raise BusinessError(APIError.VIDEO_NOT_FOUND)

        comment = Comment(
            video_id=video_id,
            user_id=user_id,
            content=content
        )

        db.session.add(comment)

        return AddCommentResponseDto(
            comment_id=comment.comment_id,
            message='댓글이 작성되었습니다.'
        )

    @staticmethod
    @transactional
    def update_comment(comment_id: str, user_id: str, content: str):
        comment = db.session.query(Comment).filter_by(
            comment_id=comment_id,
            is_deleted=0
        ).first()

        if not comment:
            raise BusinessError(APIError.COMMENT_NOT_FOUND)

        if comment.user_id != user_id:
            raise BusinessError(APIError.COMMENT_FORBIDDEN)

        comment.content = content
        comment.is_modified = 1

    @staticmethod
    @transactional
    def delete_comment(comment_id: str, user_id: str):
        comment = db.session.query(Comment).filter_by(
            comment_id=comment_id,
            is_deleted=0
        ).first()

        if not comment:
            raise BusinessError(APIError.COMMENT_NOT_FOUND)

        if comment.user_id != user_id:
            raise BusinessError(APIError.COMMENT_FORBIDDEN)

        comment.is_deleted = 1

    @staticmethod
    @transactional
    def toggle_like(video_id: str, user_id: str) -> ToggleLikeResponseDto:
        video = db.session.query(Video).filter_by(video_id=video_id, is_deleted=0).first()
        if not video:
            raise BusinessError(APIError.VIDEO_NOT_FOUND)

        like = db.session.query(VideoLike).filter_by(
            video_id=video_id,
            user_id=user_id
        ).first()

        if like:
            db.session.delete(like)
            db.session.flush()

            like_count = db.session.query(VideoLike).filter_by(video_id=video_id).count()

            return ToggleLikeResponseDto(
                is_liked=False,
                like_count=like_count,
                message='좋아요가 취소되었습니다.'
            )
        else:
            new_like = VideoLike(
                video_id=video_id,
                user_id=user_id
            )
            db.session.add(new_like)
            db.session.flush()

            like_count = db.session.query(VideoLike).filter_by(video_id=video_id).count()

            return ToggleLikeResponseDto(
                is_liked=True,
                like_count=like_count,
                message='좋아요가 추가되었습니다.'
            )
