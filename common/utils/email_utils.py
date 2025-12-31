import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
from common.extensions import redis_client
from common.utils.logging_utils import get_logger

logger = get_logger('email_utils')


def generate_verification_code(length=6):
    return ''.join(random.choices(string.digits, k=length))


def store_verification_code(email: str, code: str, expire_seconds=300):
    if redis_client is None:
        raise RuntimeError("Redis 연결이 필요한 기능입니다. Redis 서버를 확인해주세요.")

    key = f"facereview:verification:{email}"
    redis_client.setex(key, expire_seconds, code)


def verify_code(email: str, code: str) -> bool:
    if redis_client is None:
        raise RuntimeError("Redis 연결이 필요한 기능입니다. Redis 서버를 확인해주세요.")

    key = f"facereview:verification:{email}"
    stored_code = redis_client.get(key)

    if stored_code and stored_code == code:
        redis_client.delete(key)
        return True

    return False


def send_verification_email(to_email: str, code: str):
    try:
        smtp_server = current_app.config.get('SMTP_SERVER', 'smtp.naver.com')
        smtp_port = current_app.config.get('SMTP_PORT', 465)
        smtp_username = current_app.config.get('SMTP_USERNAME')
        smtp_password = current_app.config.get('SMTP_PASSWORD')
        from_email = current_app.config.get('SMTP_FROM_EMAIL', smtp_username)

        msg = MIMEMultipart('alternative')
        msg['Subject'] = '[FaceReview] 이메일 인증번호'
        msg['From'] = from_email
        msg['To'] = to_email

        html_body = f"""
        <!DOCTYPE html>
        <html>
          <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
          </head>
          <body style="margin: 0; padding: 0; background-color: #0a0a0f; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #0a0a0f; padding: 50px 20px;">
              <tr>
                <td align="center">
                  <table width="600" cellpadding="0" cellspacing="0" style="max-width: 600px; background-color: #15151d; border-radius: 20px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4); overflow: hidden; border: 1px solid #25252f;">

                    <!-- 헤더 (로고 영역) -->
                    <tr>
                      <td style="background-color: #15151d; padding: 50px 40px 30px 40px; text-align: center;">
                        <img src="https://winterholic.github.io/my-gallery/images/facereview-logo.svg" alt="FaceReview Logo" style="height: 60px; margin-bottom: 25px;">
                        <h1 style="color: #ffffff; margin: 0; font-size: 32px; font-weight: 700; letter-spacing: -1px;">이메일 인증</h1>
                        <div style="width: 60px; height: 4px; background: linear-gradient(90deg, #76ffce 0%, #5ce1b8 100%); margin: 20px auto 0; border-radius: 2px;"></div>
                      </td>
                    </tr>

                    <!-- 본문 -->
                    <tr>
                      <td style="padding: 40px 40px 50px 40px;">
                        <p style="color: #b8b8c0; font-size: 16px; line-height: 1.8; margin: 0 0 35px 0; text-align: center;">
                          안녕하세요! <span style="color: #76ffce; font-weight: 600;">FaceReview</span>입니다.<br>
                          아래의 인증번호를 입력하여 이메일 인증을 완료해주세요.
                        </p>

                        <!-- 인증번호 박스 -->
                        <div style="background: linear-gradient(135deg, #393946 0%, #25252f 100%); border-radius: 16px; padding: 40px 30px; text-align: center; margin: 35px 0; border: 2px solid #76ffce; box-shadow: 0 0 30px rgba(118, 255, 206, 0.15);">
                          <p style="color: #76ffce; font-size: 13px; margin: 0 0 15px 0; letter-spacing: 3px; text-transform: uppercase; font-weight: 600;">VERIFICATION CODE</p>
                          <h2 style="color: #ffffff; margin: 0; font-size: 48px; font-weight: 700; letter-spacing: 12px; font-family: 'Courier New', monospace; text-shadow: 0 0 20px rgba(118, 255, 206, 0.3);">{code}</h2>
                        </div>

                        <!-- 안내 사항 -->
                        <div style="background-color: #1a1a24; border-left: 3px solid #76ffce; padding: 25px; border-radius: 12px; margin-top: 35px;">
                          <p style="color: #9494a0; font-size: 14px; line-height: 1.8; margin: 0;">
                            <span style="color: #76ffce; font-weight: 600;">⚡ 안내사항</span><br><br>
                            <span style="color: #c0c0c8;">•</span> 인증번호는 <span style="color: #76ffce; font-weight: 600;">5분간</span> 유효합니다<br>
                            <span style="color: #c0c0c8;">•</span> 본인이 요청하지 않았다면 이 메일을 무시하세요<br>
                            <span style="color: #c0c0c8;">•</span> 인증번호는 타인에게 절대 공유하지 마세요
                          </p>
                        </div>
                      </td>
                    </tr>

                    <!-- 푸터 -->
                    <tr>
                      <td style="background-color: #0f0f17; padding: 35px 40px; text-align: center; border-top: 1px solid #25252f;">
                        <p style="color: #6a6a78; font-size: 13px; line-height: 1.8; margin: 0;">
                          이 메일은 발신 전용입니다. 문의사항은 고객센터를 이용해주세요.<br>
                          <span style="color: #76ffce; font-weight: 600;">FaceReview</span> <span style="color: #494952;">© 2025 All rights reserved.</span>
                        </p>
                      </td>
                    </tr>

                  </table>
                </td>
              </tr>
            </table>
          </body>
        </html>
        """

        text_body = f"""
        FaceReview 이메일 인증

        안녕하세요! FaceReview입니다.
        아래 인증번호를 입력해주세요.

        인증번호: {code}

        인증번호는 5분간 유효합니다.
        본인이 요청하지 않았다면 이 메일을 무시하세요.
        """

        part1 = MIMEText(text_body, 'plain')
        part2 = MIMEText(html_body, 'html')

        msg.attach(part1)
        msg.attach(part2)

        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
                if smtp_username and smtp_password:
                    server.login(smtp_username, smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                if smtp_username and smtp_password:
                    server.login(smtp_username, smtp_password)
                server.send_message(msg)

        return True

    except Exception as e:
        logger.error(f"Error sending verification email: {e}")
        return False


def generate_password_reset_token() -> str:
    import uuid
    return str(uuid.uuid4())


def store_password_reset_token(email: str, token: str, expire_seconds=600):
    if redis_client is None:
        raise RuntimeError("Redis 연결이 필요한 기능입니다. Redis 서버를 확인해주세요.")

    key = f"facereview:password_reset:{token}"
    redis_client.setex(key, expire_seconds, email)


def verify_password_reset_token(token: str) -> str:
    if redis_client is None:
        raise RuntimeError("Redis 연결이 필요한 기능입니다. Redis 서버를 확인해주세요.")

    key = f"facereview:password_reset:{token}"
    email = redis_client.get(key)

    if email:
        redis_client.delete(key)
        return email

    return None
