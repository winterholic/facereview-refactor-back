import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(app=None, log_level=None):
    if log_level is None:
        log_level = logging.INFO

    if app:
        logger = app.logger
        logger.setLevel(log_level)
    else:
        logger = logging.getLogger('facereview')
        logger.setLevel(log_level)

    if logger.handlers:
        return logger

    #NOTE: 한글 로그를 위한 UTF-8 인코딩 설정
    formatter = logging.Formatter(
        fmt='[%(asctime)s] %(levelname)s in %(name)s (%(filename)s:%(lineno)d): %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    #NOTE: 콘솔 핸들러 - stdout으로 출력
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    #NOTE: 파일 핸들러 - 로그 파일로 저장 (10MB 단위로 로테이션, 최대 5개 파일)
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)

    file_handler = RotatingFileHandler(
        log_dir / 'facereview.log',
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    #NOTE: 에러 로그 별도 파일 저장
    error_handler = RotatingFileHandler(
        log_dir / 'error.log',
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)

    return logger


def get_logger(name=None):
    if name:
        return logging.getLogger(f'facereview.{name}')
    return logging.getLogger('facereview')
