from marshmallow import Schema, fields, validate

class SearchVideoRequestSchema(Schema):
    page = fields.Int(
        required=True,  # 필수 조건
        validate=validate.Range(min=1),
        metadata={'description': '페이지 번호 (1 이상)'}
    )
    size = fields.Int(
        required=True,  # 필수 조건
        validate=validate.Range(min=1, max=100),
        metadata={'description': '페이지 당 개수 (최대 100)'}
    )
    keyword_type = fields.String(
        required=True,  # 필수 조건
        metadata={'description': '검색어 타입 (all, title, channel_name)'}
    )
    keyword = fields.String(
        required=True,  # 필수 조건
        metadata={'description': '검색어'}
    )
    
class VideoResponseSchema(Schema):
    video_id = fields.String(metadata={'description': '영상 UUID'})
    youtube_url = fields.String(metadata={'description': '유튜브 URL'})
    title = fields.String(metadata={'description': '영상 제목'})
    dominant_emotion = fields.String(metadata={'description': '주된 감정 (예: happy, sad)'})
    dominant_emotion_per = fields.Float(metadata={'description': '주된 감정의 백분율 (0.0 ~ 100.0)'})

class SearchVideoResponseSchema(Schema):
    videos = fields.List(
        fields.Nested(VideoResponseSchema()),
        metadata={'description': '영상 리스트'}
    )
    total = fields.Int(metadata={'description': '전체 영상 개수'})
    page = fields.Int(metadata={'description': '현재 페이지'})
    size = fields.Int(metadata={'description': '페이지 당 개수'})
    has_next = fields.Bool(metadata={'description': '다음 페이지 존재 여부'})

class AllVideoResponseSchema(Schema):
    videos = fields.List(
        fields.Nested(VideoResponseSchema()),
        metadata={'description': '영상 리스트'}
    )
    total = fields.Int(metadata={'description': '전체 영상 개수'})
    page = fields.Int(metadata={'description': '현재 페이지'})
    size = fields.Int(metadata={'description': '페이지 당 개수'})
    has_next = fields.Bool(metadata={'description': '다음 페이지 존재 여부'})

class EmotionVideoQuerySchema(Schema):
    page = fields.Int(
        required=True,  # 필수 조건
        validate=validate.Range(min=1),
        metadata={'description': '페이지 번호 (1 이상)'}
    )
    size = fields.Int(
        required=True,  # 필수 조건
        validate=validate.Range(min=1, max=100),
        metadata={'description': '페이지 당 개수 (최대 100)'}
    )
    emotion = fields.String(
        required=True,  # 필수 조건
        metadata={'description': '감정 필터 (all, happy, sad, neutral, surprise, angry)'}
    )

class CategoryGroupedResponseSchema(Schema):
    category_name = fields.String()
    videos = fields.List(fields.Nested(VideoResponseSchema()))

class CategoryRecommendVideoResponseSchema(Schema):
    video_data = fields.List(fields.Nested(CategoryGroupedResponseSchema()))

class VideoRecommendRequestSchema(Schema):
    youtube_url = fields.String(
        required=True,
        validate=validate.Length(min=1),
        metadata={'description': '추천할 유튜브 URL'}
    )