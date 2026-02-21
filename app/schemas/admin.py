from marshmallow import Schema, fields, validate
from common.enum.youtube_genre import GenreEnum


class GetUsersRequestSchema(Schema):
    keyword = fields.String(
        load_default=None,
        metadata={'description': '검색어 (이름 또는 이메일, 선택)'}
    )
    is_deleted = fields.Boolean(
        load_default=None,
        metadata={'description': '탈퇴 회원 필터 (true: 탈퇴 회원만, false: 활성 회원만, 미입력: 전체)'}
    )
    page = fields.Integer(
        load_default=1,
        validate=validate.Range(min=1),
        metadata={'description': '페이지 번호 (1부터 시작)'}
    )
    size = fields.Integer(
        load_default=20,
        validate=validate.Range(min=1, max=100),
        metadata={'description': '페이지 크기 (1~100)'}
    )


class AdminUserSchema(Schema):
    user_id = fields.String(metadata={'description': '사용자 ID'})
    email = fields.String(metadata={'description': '이메일'})
    name = fields.String(metadata={'description': '사용자 이름'})
    role = fields.String(metadata={'description': '권한 (GENERAL/ADMIN)'})
    profile_image_id = fields.Integer(metadata={'description': '프로필 이미지 ID'})
    is_tutorial_done = fields.Boolean(metadata={'description': '튜토리얼 완료 여부'})
    is_verify_email_done = fields.Boolean(metadata={'description': '이메일 인증 완료 여부'})
    is_deleted = fields.Boolean(metadata={'description': '탈퇴 여부'})
    created_at = fields.String(metadata={'description': '가입일시 (ISO 8601)'})
    total_watch_count = fields.Integer(metadata={'description': '총 시청 횟수'})
    total_comment_count = fields.Integer(metadata={'description': '총 댓글 수'})


class GetUsersResponseSchema(Schema):
    users = fields.List(fields.Nested(AdminUserSchema), metadata={'description': '사용자 목록'})
    total = fields.Integer(metadata={'description': '전체 개수'})
    page = fields.Integer(metadata={'description': '현재 페이지'})
    size = fields.Integer(metadata={'description': '페이지 크기'})
    has_next = fields.Boolean(metadata={'description': '다음 페이지 존재 여부'})


class DeactivateUserResponseSchema(Schema):
    message = fields.String(metadata={'description': '성공 메시지'})


class ChangeUserRoleRequestSchema(Schema):
    role = fields.String(
        required=True,
        validate=validate.OneOf(['GENERAL', 'ADMIN']),
        metadata={'description': '변경할 권한 (GENERAL/ADMIN)'}
    )


class ChangeUserRoleResponseSchema(Schema):
    message = fields.String(metadata={'description': '성공 메시지'})


class GetVideoRequestsRequestSchema(Schema):
    status = fields.String(
        load_default=None,
        validate=validate.OneOf(['PENDING', 'ACCEPTED', 'REJECTED']),
        metadata={'description': '상태 필터 (PENDING/ACCEPTED/REJECTED, 선택)'}
    )
    page = fields.Integer(
        load_default=1,
        validate=validate.Range(min=1),
        metadata={'description': '페이지 번호 (1부터 시작)'}
    )
    size = fields.Integer(
        load_default=20,
        validate=validate.Range(min=1, max=100),
        metadata={'description': '페이지 크기 (1~100)'}
    )


class VideoRequestSchema(Schema):
    video_request_id = fields.String(metadata={'description': '영상 요청 ID'})
    user_id = fields.String(metadata={'description': '요청 사용자 ID'})
    user_name = fields.String(metadata={'description': '요청 사용자 이름'})
    youtube_url = fields.String(metadata={'description': '유튜브 영상 ID'})
    youtube_full_url = fields.String(metadata={'description': '유튜브 전체 URL'})
    category = fields.String(metadata={'description': '카테고리'})
    status = fields.String(metadata={'description': '처리 상태'})
    admin_comment = fields.String(metadata={'description': '관리자 코멘트'})
    created_at = fields.String(metadata={'description': '요청일시 (ISO 8601)'})
    updated_at = fields.String(metadata={'description': '처리일시 (ISO 8601)'})


class GetVideoRequestsResponseSchema(Schema):
    requests = fields.List(fields.Nested(VideoRequestSchema), metadata={'description': '영상 요청 목록'})
    total = fields.Integer(metadata={'description': '전체 개수'})
    page = fields.Integer(metadata={'description': '현재 페이지'})
    size = fields.Integer(metadata={'description': '페이지 크기'})
    has_next = fields.Boolean(metadata={'description': '다음 페이지 존재 여부'})


class ApproveVideoRequestRequestSchema(Schema):
    youtube_title = fields.String(
        required=True,
        validate=validate.Length(min=1, max=255),
        metadata={'description': '유튜브 영상 제목'}
    )
    channel_name = fields.String(
        required=True,
        validate=validate.Length(min=1, max=100),
        metadata={'description': '채널명'}
    )
    duration = fields.Integer(
        required=True,
        validate=validate.Range(min=1),
        metadata={'description': '영상 길이 (초)'}
    )


class ApproveVideoRequestResponseSchema(Schema):
    video_id = fields.String(metadata={'description': '생성된 영상 ID'})
    message = fields.String(metadata={'description': '성공 메시지'})


class RejectVideoRequestRequestSchema(Schema):
    admin_comment = fields.String(
        required=True,
        validate=validate.Length(min=1, max=255),
        metadata={'description': '거절 사유'}
    )


class RejectVideoRequestResponseSchema(Schema):
    message = fields.String(metadata={'description': '성공 메시지'})


class GetVideosRequestSchema(Schema):
    keyword = fields.String(
        load_default=None,
        metadata={'description': '검색어 (제목 또는 채널명, 선택)'}
    )
    category = fields.String(
        load_default=None,
        validate=validate.OneOf([e.value for e in GenreEnum]),
        metadata={'description': '카테고리 필터 (선택)'}
    )
    page = fields.Integer(
        load_default=1,
        validate=validate.Range(min=1),
        metadata={'description': '페이지 번호 (1부터 시작)'}
    )
    size = fields.Integer(
        load_default=20,
        validate=validate.Range(min=1, max=100),
        metadata={'description': '페이지 크기 (1~100)'}
    )


class AdminVideoSchema(Schema):
    video_id = fields.String(metadata={'description': '영상 ID'})
    youtube_url = fields.String(metadata={'description': '유튜브 영상 ID'})
    title = fields.String(metadata={'description': '영상 제목'})
    channel_name = fields.String(metadata={'description': '채널명'})
    category = fields.String(metadata={'description': '카테고리'})
    duration = fields.Integer(metadata={'description': '영상 길이 (초)'})
    view_count = fields.Integer(metadata={'description': '조회수'})
    like_count = fields.Integer(metadata={'description': '좋아요 수'})
    comment_count = fields.Integer(metadata={'description': '댓글 수'})
    created_at = fields.String(metadata={'description': '등록일시 (ISO 8601)'})
    is_deleted = fields.Boolean(metadata={'description': '삭제 여부'})


class GetVideosResponseSchema(Schema):
    videos = fields.List(fields.Nested(AdminVideoSchema), metadata={'description': '영상 목록'})
    total = fields.Integer(metadata={'description': '전체 개수'})
    page = fields.Integer(metadata={'description': '현재 페이지'})
    size = fields.Integer(metadata={'description': '페이지 크기'})
    has_next = fields.Boolean(metadata={'description': '다음 페이지 존재 여부'})


class DeleteVideoResponseSchema(Schema):
    message = fields.String(metadata={'description': '성공 메시지'})


class GetCommentsRequestSchema(Schema):
    video_id = fields.String(
        load_default=None,
        metadata={'description': '영상 ID 필터 (선택)'}
    )
    keyword = fields.String(
        load_default=None,
        metadata={'description': '댓글 내용 검색 (선택)'}
    )
    is_deleted = fields.Boolean(
        load_default=None,
        metadata={'description': '삭제 댓글 필터 (true: 삭제 댓글만, false: 정상 댓글만, 미입력: 전체)'}
    )
    page = fields.Integer(
        load_default=1,
        validate=validate.Range(min=1),
        metadata={'description': '페이지 번호 (1부터 시작)'}
    )
    size = fields.Integer(
        load_default=20,
        validate=validate.Range(min=1, max=100),
        metadata={'description': '페이지 크기 (1~100)'}
    )


class AdminCommentSchema(Schema):
    comment_id = fields.String(metadata={'description': '댓글 ID'})
    video_id = fields.String(metadata={'description': '영상 ID'})
    video_title = fields.String(metadata={'description': '영상 제목'})
    user_id = fields.String(metadata={'description': '작성자 ID'})
    user_name = fields.String(metadata={'description': '작성자 이름'})
    content = fields.String(metadata={'description': '댓글 내용'})
    is_modified = fields.Boolean(metadata={'description': '수정 여부'})
    is_deleted = fields.Boolean(metadata={'description': '삭제 여부'})
    created_at = fields.String(metadata={'description': '작성일시 (ISO 8601)'})


class GetCommentsResponseSchema(Schema):
    comments = fields.List(fields.Nested(AdminCommentSchema), metadata={'description': '댓글 목록'})
    total = fields.Integer(metadata={'description': '전체 개수'})
    page = fields.Integer(metadata={'description': '현재 페이지'})
    size = fields.Integer(metadata={'description': '페이지 크기'})
    has_next = fields.Boolean(metadata={'description': '다음 페이지 존재 여부'})


class DeleteCommentResponseSchema(Schema):
    message = fields.String(metadata={'description': '성공 메시지'})


class ServerStatusSchema(Schema):
    cpu_usage = fields.Float(metadata={'description': 'CPU 사용률 (%)'})
    memory_usage = fields.Float(metadata={'description': '메모리 사용률 (%)'})
    memory_total_mb = fields.Float(metadata={'description': '총 메모리 (MB)'})
    disk_usage = fields.Float(metadata={'description': '디스크 사용률 (%)'})


class ApiStatusSchema(Schema):
    total_requests_1h = fields.Integer(metadata={'description': '최근 1시간 요청 수'})
    avg_response_time_ms = fields.Float(metadata={'description': '평균 응답 시간 (ms)'})
    error_rate_1h = fields.Float(metadata={'description': '최근 1시간 에러율 (%)'})


class ConnectionStatusSchema(Schema):
    mysql = fields.String(metadata={'description': 'MySQL 연결 상태 (ok/error)'})
    redis = fields.String(metadata={'description': 'Redis 연결 상태 (ok/error)'})
    mongodb = fields.String(metadata={'description': 'MongoDB 연결 상태 (ok/error)'})


class SystemStatusResponseSchema(Schema):
    server = fields.Nested(ServerStatusSchema, metadata={'description': '서버 리소스 상태'})
    api = fields.Nested(ApiStatusSchema, metadata={'description': 'API 요청 통계'})
    connections = fields.Nested(ConnectionStatusSchema, metadata={'description': 'DB/인프라 연결 상태'})
    checked_at = fields.String(metadata={'description': '조회 시각 (ISO 8601)'})


class GenerateDummyDataResponseSchema(Schema):
    message = fields.String(metadata={'description': '처리 결과 메시지'})
    created_count = fields.Integer(metadata={'description': '생성된 시청 기록 수'})
    user_id = fields.String(metadata={'description': '데이터가 생성된 유저 ID'})
    video_ids = fields.List(fields.String(), metadata={'description': '더미 데이터가 생성된 영상 ID 목록'})
