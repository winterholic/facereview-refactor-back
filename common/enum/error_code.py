from enum import Enum

class APIError(Enum):
    # 1. 공통 에러
    INTERNAL_SERVER_ERROR = ("C001", "서버 내부 오류가 발생했습니다.", 500)
    INVALID_INPUT_VALUE  = ("C002", "입력값이 올바르지 않습니다.", 400)
    DB_ERROR = ("C003", "DB 작업 처리 중 오류가 발생하였습니다.", 400)

    # 2. 인증(Auth) 관련
    AUTH_TOKEN_EXPIRED   = ("A001", "토큰이 만료되었습니다.", 401)
    AUTH_INVALID_TOKEN   = ("A002", "유효하지 않은 토큰입니다.", 401)
    AUTH_INVALID_EMAIL    = ("A003", "유효하지 않은 이메일입니다.", 400)
    AUTH_INVALID_PASSWORD = ("A004", "유효하지 않은 비밀번호입니다.", 400)
    AUTH_DUPLICATE_EMAIL = ("A005", "이미 가입된 이메일입니다.", 409)
    AUTH_INVALID_VERIFICATION_CODE = ("A006", "유효하지 않은 인증 코드입니다.", 400)

    # 3. 사용자(User) 관련
    USER_NOT_FOUND       = ("U001", "사용자를 찾을 수 없습니다.", 404)

    # 4. 영상(Video) 관련
    VIDEO_NOT_FOUND      = ("V001", "영상을 찾을 수 없습니다.", 404)
    VIDEO_PROCESS_FAIL   = ("V002", "영상 처리에 실패했습니다.", 500)
    VIDEO_DUPLICATE_URL   = ("V003", "이미 FaceReview에 등록된 영상입니다..", 409)
    VIDEO_REQUEST_DUPLICATE_URL   = ("V004", "이미 FaceReview에 등록 신청된 영상입니다..", 409)

    # 5. 댓글(Comment) 관련
    COMMENT_NOT_FOUND    = ("M001", "댓글을 찾을 수 없습니다.", 404)
    COMMENT_FORBIDDEN    = ("M002", "댓글에 대한 권한이 없습니다.", 403)

    def __init__(self, code, message, status):
        self.code = code
        self.message = message
        self.status = status