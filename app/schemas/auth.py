from marshmallow import Schema, fields, validate

from common.enum.youtube_genre import GenreEnum

class UserResponseSchema(Schema):
    user_id = fields.String(metadata={'description': '사용자 고유 UUID'})
    email = fields.Email(metadata={'description': '이메일'})
    name = fields.String(metadata={'description': '사용자 이름 (닉네임)'})
    profile_image_id = fields.Integer(metadata={'description': '프로필 이미지 ID'})
    is_tutorial_done = fields.Boolean(metadata={'description': '튜토리얼 완료 여부'})
    is_verify_email_done = fields.Boolean(metadata={'description': '이메일 인증 완료 여부'})
    role = fields.String(metadata={'description': '사용자 권한 (GENERAL, ADMIN)'})
    created_at = fields.DateTime(metadata={'description': '가입일'})
    favorite_genres = fields.List(
        fields.String(
            validate=validate.OneOf(
                [e.value for e in GenreEnum],
                error="지원하지 않는 장르입니다."
            )
        ),
        metadata={'description': '선호 장르 목록'}
    )

class EmailCheckRequestSchema(Schema):
    email = fields.Email(required=True, metadata={'description': '확인할 이메일'})

class EmailCheckResponseSchema(Schema):
    is_duplicate = fields.Boolean(required=True, metadata={'description': '이메일 중복 여부 False면 중복된 이메일 없고 True면 있음'})
    message = fields.String(required=True, metadata={'description': '안내 메시지'})

class SignupRequestSchema(Schema):
    email = fields.Email(required=True, metadata={'description': '이메일'})
    password = fields.String(
        required=True,
        validate=validate.Length(min=8),
        metadata={'description': '비밀번호 (최소 8자)'}
    )
    name = fields.String(
        required=True,
        validate=validate.Length(min=2, max=10),
        metadata={'description': '사용자 이름 (2~10자)'}
    )
    favorite_genres = fields.List(
        fields.String(
            validate=validate.OneOf(
                [e.value for e in GenreEnum],
                error="지원하지 않는 장르입니다."
            )
        ),
        metadata={'description': '선호 장르 목록'}
    )

class LoginRequestSchema(Schema):
    email = fields.Email(required=True, metadata={'description': '이메일'})
    password = fields.String(required=True, metadata={'description': '비밀번호'})

class LoginResponseSchema(Schema):
    access_token = fields.String(required=True, metadata={'description': 'JWT 액세스 토큰'})
    refresh_token = fields.String(required=True, metadata={'description': 'JWT 리프레시 토큰'})


class AccessTokenResponseSchema(Schema):
    access_token = fields.String(required=True, metadata={'description': 'JWT 액세스 토큰'})

class TestTokenResponseSchema(Schema):
    access_token = fields.String(required=True, metadata={'description': 'JWT 액세스 토큰'})
    refresh_token = fields.String(required=True, metadata={'description': 'JWT 리프레시 토큰'})

class CheckResponseSchema(Schema):
    is_duplicate = fields.Boolean(metadata={'description': '중복 여부 (True: 중복됨/로그인으로, False: 사용가능/회원가입으로)'})
    message = fields.String(metadata={'description': '안내 메시지'})

class LogoutRequestSchema(Schema):
    token = fields.String(required=True, metadata={'description': '블랙리스트 처리할 토큰'})

class ReissueRequestSchema(Schema):
    refresh_token = fields.String(required=True, metadata={'description': '리프레시 토큰'})