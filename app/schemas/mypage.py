from marshmallow import Schema, fields, validate
from common.enum.youtube_genre import GenreEnum


class TimelineEmotionPointSchema(Schema):
    x = fields.Integer(metadata={'description': '시간 인덱스 (0부터 시작)'})
    y = fields.Float(metadata={'description': '감정 비율 (0.0 ~ 100.0)'})


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


class VerifyCodeForPasswordResetRequestSchema(Schema):
    code = fields.String(required=True, validate=validate.Length(equal=6), metadata={'description': '인증번호 (6자리)'})


class VerifyCodeForPasswordResetResponseSchema(Schema):
    reset_token = fields.String(metadata={'description': '비밀번호 재설정 토큰 (UUID)'})
    message = fields.String(metadata={'description': '안내 메시지'})


class ChangePasswordRequestSchema(Schema):
    reset_token = fields.String(required=True, metadata={'description': '비밀번호 재설정 토큰'})
    new_password = fields.String(
        required=True,
        validate=validate.Length(min=8, max=64),
        metadata={'description': '새 비밀번호 (8~64자)'}
    )


# ==================== 1.1 최근 시청 ====================

class GetRecentVideosRequestSchema(Schema):
    emotion = fields.String(
        load_default='all',
        validate=validate.OneOf(['all', 'neutral', 'happy', 'surprise', 'sad', 'angry']),
        metadata={'description': '감정 필터 (all 또는 특정 감정)'}
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


class RecentVideoSchema(Schema):
    video_id = fields.String(metadata={'description': '영상 UUID'})
    youtube_url = fields.String(metadata={'description': '유튜브 URL'})
    title = fields.String(metadata={'description': '영상 제목'})
    dominant_emotion = fields.String(metadata={'description': '주된 감정 (neutral, happy, surprise, sad, angry)'})
    dominant_emotion_per = fields.Float(metadata={'description': '주된 감정 비율 (0.0 ~ 100.0)'})
    watched_at = fields.String(metadata={'description': '시청일시 (ISO 8601)'})
    timeline_data = fields.Dict(
        keys=fields.String(),
        values=fields.List(fields.Nested(TimelineEmotionPointSchema)),
        metadata={'description': '감정별 타임라인 데이터 (키: 감정명, 값: x/y 포인트 리스트)'}
    )


class RecentVideoListResponseSchema(Schema):
    videos = fields.List(fields.Nested(RecentVideoSchema), metadata={'description': '최근 시청 영상 목록'})
    total = fields.Integer(metadata={'description': '전체 영상 수'})
    page = fields.Integer(metadata={'description': '현재 페이지'})
    size = fields.Integer(metadata={'description': '페이지 크기'})
    has_next = fields.Boolean(metadata={'description': '다음 페이지 존재 여부'})


# ==================== 1.2 감정 요약 ====================

class EmotionSummaryResponseSchema(Schema):
    emotion_percentages = fields.Dict(
        keys=fields.String(),
        values=fields.Float(),
        metadata={'description': '감정별 비율 (키: 감정명, 값: 0.0~100.0)'}
    )
    emotion_seconds = fields.Dict(
        keys=fields.String(),
        values=fields.Integer(),
        metadata={'description': '감정별 누적 시청 시간 (키: 감정명, 값: 초)'}
    )


# ==================== 1.3 하이라이트 ====================

class EmotionVideoSchema(Schema):
    emotion = fields.String(metadata={'description': '감정 종류'})
    video_id = fields.String(metadata={'description': '영상 UUID'})
    youtube_url = fields.String(metadata={'description': '유튜브 URL'})
    title = fields.String(metadata={'description': '영상 제목'})
    emotion_percentage = fields.Float(metadata={'description': '해당 감정 비율 (0.0~1.0)'})


class CategoryEmotionHighlightSchema(Schema):
    category = fields.String(metadata={'description': '카테고리명'})
    dominant_emotion = fields.String(metadata={'description': '카테고리의 대표 감정'})
    percentage = fields.Float(metadata={'description': '대표 감정 비율 (0.0~100.0)'})


class HighlightResponseSchema(Schema):
    emotion_videos = fields.List(
        fields.Nested(EmotionVideoSchema),
        metadata={'description': '감정별 대표 영상 목록 (최대 5개)'}
    )
    category_emotions = fields.List(
        fields.Nested(CategoryEmotionHighlightSchema),
        metadata={'description': '카테고리별 대표 감정 목록'}
    )
    most_watched_category = fields.String(metadata={'description': '가장 많이 시청한 카테고리'})
    most_felt_emotion = fields.String(metadata={'description': '가장 많이 느낀 감정'})


# ==================== 2.1 감정 캘린더 ====================

class GetEmotionCalendarRequestSchema(Schema):
    year = fields.Integer(
        load_default=None,
        metadata={'description': '조회 연도 (미입력 시 현재 연도)'}
    )
    month = fields.Integer(
        load_default=None,
        validate=validate.Range(min=1, max=12),
        metadata={'description': '조회 월 (미입력 시 연도 전체)'}
    )


class CalendarDaySchema(Schema):
    date = fields.String(metadata={'description': '날짜 (YYYY-MM-DD)'})
    dominant_emotion = fields.String(metadata={'description': '해당 날짜의 주요 감정'})
    intensity = fields.Float(metadata={'description': '감정 강도 (0.0~1.0)'})
    watch_count = fields.Integer(metadata={'description': '시청 횟수'})
    total_watch_time = fields.Integer(metadata={'description': '총 시청 시간 (초)'})


class EmotionCalendarResponseSchema(Schema):
    year = fields.Integer(metadata={'description': '조회 연도'})
    month = fields.Integer(allow_none=True, metadata={'description': '조회 월 (전체 조회 시 null)'})
    data = fields.List(fields.Nested(CalendarDaySchema), metadata={'description': '일자별 감정 데이터'})


# ==================== 2.2 베스트 모먼트 ====================

class GetMomentsRequestSchema(Schema):
    emotion = fields.String(
        load_default='all',
        validate=validate.OneOf(['all', 'neutral', 'happy', 'surprise', 'sad', 'angry']),
        metadata={'description': '감정 필터 (all 또는 특정 감정)'}
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


class MomentSchema(Schema):
    video_id = fields.String(metadata={'description': '영상 UUID'})
    video_title = fields.String(metadata={'description': '영상 제목'})
    youtube_url = fields.String(metadata={'description': '유튜브 URL'})
    timestamp_seconds = fields.Float(metadata={'description': '영상 내 타임스탬프 (초)'})
    emotion = fields.String(metadata={'description': '감지된 감정'})
    emotion_percentage = fields.Float(metadata={'description': '감정 강도 (0.0 ~ 100.0)'})
    thumbnail_url = fields.String(metadata={'description': '썸네일 URL (YouTube hqdefault)'})
    watched_at = fields.String(metadata={'description': '시청일시 (ISO 8601)'})


class MomentListResponseSchema(Schema):
    moments = fields.List(fields.Nested(MomentSchema), metadata={'description': '베스트 모먼트 목록'})
    total = fields.Integer(metadata={'description': '전체 모먼트 수'})
    has_next = fields.Boolean(metadata={'description': '다음 페이지 존재 여부'})


# ==================== 2.3 감정 DNA ====================

class DnaTraitSchema(Schema):
    trait = fields.String(metadata={'description': '특성 이름'})
    score = fields.Integer(metadata={'description': '특성 점수 (0~100)'})


class EmotionDnaResponseSchema(Schema):
    dna_type = fields.String(metadata={'description': 'DNA 유형 코드'})
    dna_title = fields.String(metadata={'description': 'DNA 유형 한글명'})
    dna_description = fields.String(metadata={'description': 'DNA 유형 설명'})
    traits = fields.List(fields.Nested(DnaTraitSchema), metadata={'description': '주요 특성 3가지'})
    emotion_radar = fields.Dict(keys=fields.String(), values=fields.Integer(), metadata={'description': '감정 레이더 (0~100)'})
    fun_facts = fields.List(fields.String(), metadata={'description': '재미있는 사실 2가지'})
    generated_at = fields.String(metadata={'description': '생성일시 (ISO 8601)'})
    based_on_videos = fields.Integer(metadata={'description': '분석 기반 시청 세션 수'})
