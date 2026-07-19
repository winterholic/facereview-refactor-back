from flask import jsonify

from common.enum.error_code import APIError
from common.exception.exceptions import BusinessError
from common.utils.logging_utils import get_logger
from sqlalchemy.exc import IntegrityError, DataError, SQLAlchemyError
from werkzeug.exceptions import HTTPException


logger = get_logger('error_handler')


def _failure_payload(message, code):
    return {
        "result": "fail",
        "message": message,
        "code": code,
        "data": None,
    }


def register_error_handlers(app):
    @app.errorhandler(BusinessError)
    def handle_business_error(e):
        return jsonify(_failure_payload(e.message, e.error_enum.code)), e.error_enum.status

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(e):
        logger.warning("데이터 무결성 오류가 발생했습니다.")
        return jsonify(_failure_payload(
            "중복된 데이터가 있거나 참조 무결성이 위배되었습니다.",
            APIError.INVALID_INPUT_VALUE.code,
        )), 400

    @app.errorhandler(DataError)
    def handle_data_error(e):
        logger.warning("데이터 형식 오류가 발생했습니다.")
        return jsonify(_failure_payload(
            "올바르지 않은 데이터 형식입니다.",
            APIError.INVALID_INPUT_VALUE.code,
        )), 400

    @app.errorhandler(SQLAlchemyError)
    def handle_db_error(e):
        logger.exception("데이터베이스 작업 중 오류가 발생했습니다.")
        return jsonify(_failure_payload(
            "데이터베이스 작업 중 오류가 발생했습니다.",
            APIError.DB_ERROR.code,
        )), APIError.DB_ERROR.status

    @app.errorhandler(HTTPException)
    def handle_http_error(e):
        if e.code == 404:
            error = APIError.ROUTE_NOT_FOUND
            return jsonify(_failure_payload(error.message, error.code)), error.status

        return jsonify(_failure_payload(
            "요청 방식 또는 경로가 올바르지 않습니다.",
            APIError.INVALID_INPUT_VALUE.code,
        )), e.code

    @app.errorhandler(Exception)
    def handle_internal_error(e):
        logger.exception("처리되지 않은 서버 오류가 발생했습니다.")
        return jsonify(_failure_payload(
            APIError.INTERNAL_SERVER_ERROR.message,
            APIError.INTERNAL_SERVER_ERROR.code,
        )), APIError.INTERNAL_SERVER_ERROR.status
