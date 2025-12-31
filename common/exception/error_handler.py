from flask import jsonify

from common.enum.error_code import APIError
from common.exception.exceptions import BusinessError
from sqlalchemy.exc import IntegrityError, DataError, SQLAlchemyError

def register_error_handlers(app):
    @app.errorhandler(BusinessError)
    def handle_business_error(e):
        return jsonify({
            "result": "fail",
            "message": e.message,
            "code": e.error_enum.code,
            "data": None
        }), e.error_enum.status

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(e):
        return jsonify({
            "result": "fail",
            "message": "중복된 데이터가 있거나 참조 무결성이 위배되었습니다.", # 혹은 구체적인 메시지 가공
            "code": APIError.INVALID_INPUT_VALUE.code
        }), 400

    @app.errorhandler(DataError)
    def handle_data_error(e):
        return jsonify({
            "result": "fail",
            "message": "올바르지 않은 데이터 형식입니다.",
            "code": APIError.INVALID_INPUT_VALUE.code
        }), 400

    @app.errorhandler(SQLAlchemyError)
    def handle_db_error(e):
        return jsonify({
            "result": "fail",
            "message": "데이터베이스 작업 중 오류가 발생했습니다.",
            "code": APIError.DB_ERROR.code
        }), 500

    @app.errorhandler(Exception)
    def handle_internal_error(e):
        return jsonify({
            "result": "fail",
            "message": "서버 내부 오류가 발생했습니다.",
            "code": "C001",
            "data": None
        }), 500