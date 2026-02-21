from marshmallow import Schema, fields, validate
from common.enum.youtube_genre import GenreEnum


class TimelineEmotionPointSchema(Schema):
    x = fields.Integer()
    y = fields.Float()


class VideoTimelineSchema(Schema):
    id = fields.String()
    data = fields.List(fields.Nested(TimelineEmotionPointSchema))


class EmotionItemSchema(Schema):
    emotion = fields.String()
    percentage = fields.Float()

class UpdateProfileRequestSchema(Schema):
    name = fields.String(validate=validate.Length(min=2, max=10), metadata={'description': '닉네임 (2~10자)'})
    profile_image_id = fields.Integer(metadata={'description': '프로필 이미지 ID'})
    favorite_genres = fields.List(
        fields.String(validate=validate.OneOf([e.value for e in GenreEnum])),
        validate=validate.Length(min=1, error="최소 1개 이상의 선호 장르를 선택해야 합니다."),
        metadata={'description': '선호 장르 목록 (보낼 경우 최소 1개 이상, 기존 데이터 무조건 포함)'}
    )

class VerifyEmailCodeRequestSchema(Schema):
    code = fields.String(required=True, validate=validate.Length(equal=6), metadata={'description': '인증번호 (6자리)'})


class VerifyEmailCodeResponseSchema(Schema):
    message = fields.String()


class VerifyCodeForPasswordResetRequestSchema(Schema):
    code = fields.String(required=True, validate=validate.Length(equal=6), metadata={'description': '인증번호 (6자리)'})


class VerifyCodeForPasswordResetResponseSchema(Schema):
    reset_token = fields.String(metadata={'description': '비밀번호 재설정 토큰 (UUID)'})
    message = fields.String()


class ChangePasswordRequestSchema(Schema):
    reset_token = fields.String(required=True, metadata={'description': '비밀번호 재설정 토큰'})
    new_password = fields.String(
        required=True,
        validate=validate.Length(min=8, max=64),
        metadata={'description': '새 비밀번호 (8~64자)'}
    )


class ChangePasswordResponseSchema(Schema):
    message = fields.String()

class GetRecentVideosRequestSchema(Schema):
    emotion = fields.String(
        load_default='all',
        validate=validate.OneOf(['all', 'neutral', 'happy', 'surprise', 'sad', 'angry']),
        metadata={'description': '감정 필터 (all 또는 특정 감정)'}
    )
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    size = fields.Integer(load_default=10, validate=validate.Range(min=1, max=50))


class RecentVideoSchema(Schema):
    video_id = fields.String()
    youtube_url = fields.String()
    title = fields.String()
    dominant_emotion = fields.String()
    dominant_emotion_per = fields.Float()
    watched_at = fields.String()
    timeline_data = fields.List(fields.Nested(VideoTimelineSchema))


class RecentVideoListResponseSchema(Schema):
    videos = fields.List(fields.Nested(RecentVideoSchema))
    total = fields.Integer()
    page = fields.Integer()
    size = fields.Integer()
    has_next = fields.Boolean()


class EmotionSummaryResponseSchema(Schema):
    emotion_percentages = fields.Dict(keys=fields.String(), values=fields.Float())
    emotion_seconds = fields.Dict(keys=fields.String(), values=fields.Integer())


class CategoryEmotionItemSchema(Schema):
    category = fields.String()
    top_emotions = fields.List(fields.Nested(EmotionItemSchema))


class CategoryEmotionListResponseSchema(Schema):
    categories = fields.List(fields.Nested(CategoryEmotionItemSchema))

class GetEmotionTrendRequestSchema(Schema):
    period = fields.String(
        required=True,
        validate=validate.OneOf(['weekly', 'monthly', 'yearly']),
        metadata={'description': '기간 (weekly/monthly/yearly)'}
    )


class EmotionTrendPointSchema(Schema):
    label = fields.String()
    neutral = fields.Float()
    happy = fields.Float()
    surprise = fields.Float()
    sad = fields.Float()
    angry = fields.Float()


class EmotionTrendResponseSchema(Schema):
    period = fields.String()
    data = fields.List(fields.Nested(EmotionTrendPointSchema))

class EmotionVideoSchema(Schema):
    emotion = fields.String()
    video_id = fields.String()
    youtube_url = fields.String()
    title = fields.String()
    emotion_percentage = fields.Float()


class CategoryEmotionHighlightSchema(Schema):
    category = fields.String()
    dominant_emotion = fields.String()
    percentage = fields.Float()


class HighlightResponseSchema(Schema):
    emotion_videos = fields.List(fields.Nested(EmotionVideoSchema))
    category_emotions = fields.List(fields.Nested(CategoryEmotionHighlightSchema))
    most_watched_category = fields.String()
    most_felt_emotion = fields.String()
