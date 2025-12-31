from marshmallow import Schema, fields, validate


class TimelinePointSchema(Schema):
    x = fields.Integer(metadata={'description': '시간 인덱스 (1부터 시작)'})
    y = fields.Float(metadata={'description': '감정 비율 (0.0 ~ 100.0)'})


class TimelineDataSchema(Schema):
    happy = fields.List(fields.Nested(TimelinePointSchema), metadata={'description': '행복 타임라인'})
    neutral = fields.List(fields.Nested(TimelinePointSchema), metadata={'description': '중립 타임라인'})
    surprise = fields.List(fields.Nested(TimelinePointSchema), metadata={'description': '놀람 타임라인'})
    sad = fields.List(fields.Nested(TimelinePointSchema), metadata={'description': '슬픔 타임라인'})
    angry = fields.List(fields.Nested(TimelinePointSchema), metadata={'description': '화남 타임라인'})


class GetVideoDetailRequestSchema(Schema):
    video_id = fields.String(
        required=True,
        metadata={'description': '영상 ID (UUID)'}
    )


class VideoDetailResponseSchema(Schema):
    video_id = fields.String(metadata={'description': '영상 ID (UUID)'})
    youtube_url = fields.String(metadata={'description': '유튜브 URL'})
    title = fields.String(metadata={'description': '영상 제목'})
    channel_name = fields.String(metadata={'description': '채널명'})
    category = fields.String(metadata={'description': '카테고리'})
    duration = fields.Integer(metadata={'description': '영상 길이 (초)'})
    view_count = fields.Integer(metadata={'description': '조회수'})
    like_count = fields.Integer(metadata={'description': '좋아요 수'})
    comment_count = fields.Integer(metadata={'description': '댓글 수'})
    user_is_liked = fields.Boolean(metadata={'description': '현재 사용자 좋아요 여부'})
    timeline_data = fields.Nested(TimelineDataSchema, metadata={'description': '타임라인 감정 데이터 (압축)'})

class GetRecommendedVideosRequestSchema(Schema):
    video_id = fields.String(
        required=True,
        metadata={'description': '현재 시청 중인 영상 ID'}
    )
    page = fields.Integer(
        load_default=1,
        validate=validate.Range(min=1),
        metadata={'description': '페이지 번호 (1부터 시작)'}
    )
    size = fields.Integer(
        load_default=10,
        validate=validate.Range(min=1, max=50),
        metadata={'description': '페이지 크기 (1~50)'}
    )


class RecommendedVideoSchema(Schema):
    video_id = fields.String(metadata={'description': '영상 ID'})
    youtube_url = fields.String(metadata={'description': '유튜브 URL'})
    title = fields.String(metadata={'description': '영상 제목'})
    dominant_emotion = fields.String(metadata={'description': '주요 감정'})
    dominant_emotion_per = fields.Float(metadata={'description': '주요 감정 비율 (0.0 ~ 100.0)'})


class RecommendedVideoListResponseSchema(Schema):
    videos = fields.List(fields.Nested(RecommendedVideoSchema), metadata={'description': '추천 영상 목록'})
    total = fields.Integer(metadata={'description': '전체 개수'})
    page = fields.Integer(metadata={'description': '현재 페이지'})
    size = fields.Integer(metadata={'description': '페이지 크기'})
    has_next = fields.Boolean(metadata={'description': '다음 페이지 존재 여부'})


class GetCommentListRequestSchema(Schema):
    video_id = fields.String(
        required=True,
        metadata={'description': '영상 ID'}
    )


class CommentSchema(Schema):
    comment_id = fields.String(metadata={'description': '댓글 ID'})
    user_id = fields.String(metadata={'description': '작성자 ID'})
    user_name = fields.String(metadata={'description': '작성자 이름'})
    user_profile_image_id = fields.Integer(metadata={'description': '작성자 프로필 이미지 ID'})
    content = fields.String(metadata={'description': '댓글 내용'})
    is_modified = fields.Boolean(metadata={'description': '수정 여부'})
    created_at = fields.String(metadata={'description': '작성일시 (ISO 8601)'})
    is_mine = fields.Boolean(metadata={'description': '내 댓글 여부'})


class CommentListResponseSchema(Schema):
    comments = fields.List(fields.Nested(CommentSchema), metadata={'description': '댓글 목록'})
    total = fields.Integer(metadata={'description': '전체 댓글 수'})


class AddCommentRequestSchema(Schema):
    video_id = fields.String(
        required=True,
        metadata={'description': '영상 ID'}
    )
    content = fields.String(
        required=True,
        validate=validate.Length(min=1, max=500),
        metadata={'description': '댓글 내용 (1~500자)'}
    )


class AddCommentResponseSchema(Schema):
    comment_id = fields.String(metadata={'description': '생성된 댓글 ID'})
    message = fields.String(metadata={'description': '성공 메시지'})

class UpdateCommentRequestSchema(Schema):
    comment_id = fields.String(
        required=True,
        metadata={'description': '댓글 ID'}
    )
    content = fields.String(
        required=True,
        validate=validate.Length(min=1, max=500),
        metadata={'description': '수정할 댓글 내용 (1~500자)'}
    )


class DeleteCommentRequestSchema(Schema):
    comment_id = fields.String(
        required=True,
        metadata={'description': '댓글 ID'}
    )


class ToggleLikeRequestSchema(Schema):
    video_id = fields.String(
        required=True,
        metadata={'description': '영상 ID'}
    )


class ToggleLikeResponseSchema(Schema):
    is_liked = fields.Boolean(metadata={'description': '현재 좋아요 상태 (True: 좋아요 됨, False: 취소됨)'})
    like_count = fields.Integer(metadata={'description': '현재 좋아요 수'})
    message = fields.String(metadata={'description': '성공 메시지'})
