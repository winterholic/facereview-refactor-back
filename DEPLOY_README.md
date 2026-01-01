# FaceReview 배포 가이드 (기존 인프라 연동)

기존 인프라(MariaDB, MongoDB, Redis, Kafka)가 이미 설치된 서버에 Flask 애플리케이션만 Docker로 배포하는 가이드입니다.

## 📋 환경 구성

### 기존 인프라 (호스트에 설치됨)
- MariaDB (localhost:3306)
- MongoDB (localhost:27017)
- Redis (localhost:6379)
- Kafka (localhost:9092)
- Nginx (호스트 또는 별도 설정)

### Docker Compose로 관리되는 서비스
- **facereview-app** - Flask 웹 애플리케이션 (포트 5000)
- **facereview-celery-worker** - Celery 백그라운드 작업 처리
- **facereview-kafka-consumer** - Kafka 이벤트 컨슈머

모든 컨테이너는 `network_mode: host`를 사용하여 호스트 네트워크로 실행됩니다.

## 🚀 배포 방법

### 1. GitHub Actions 자동 배포 (권장)

main 브랜치에 push하면 자동으로 배포됩니다.

```bash
git add .
git commit -m "Deploy to production"
git push origin main
```

### 2. 서버에서 직접 배포

```bash
# 서버 접속
ssh winterholic@your-server

# 프로젝트 디렉토리로 이동
cd /home/winterholic/projects/services/new-facereview

# 배포 스크립트 실행
./scripts/deploy.sh
```

## 📁 디렉토리 구조

```
/home/winterholic/projects/services/new-facereview/
├── .env                    # 환경변수 설정 (GitHub Actions가 자동 생성)
├── docker-compose.yml      # Docker Compose 설정
├── Dockerfile             # 애플리케이션 이미지
├── scripts/
│   └── deploy.sh          # 배포 스크립트
├── logs/                  # 로그 파일
└── uploads/               # 업로드 파일
```

## 🔧 환경변수 설정 (.env)

`.env` 파일에 다음 환경변수를 설정해야 합니다:

```bash
# Flask
FLASK_APP=run.py
FLASK_ENV=production
SECRET_KEY=your-secret-key

# MariaDB (호스트 서버의 DB)
DB_USERNAME=facereview
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=3306
DB_NAME=facereview

# MongoDB (호스트 서버의 DB)
MONGO_HOST=localhost
MONGO_PORT=27017
MONGO_DB_NAME=facereview

# JWT
JWT_SECRET_KEY=your-jwt-secret

# Redis (호스트 서버의 Redis)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# YouTube API
YOUTUBE_API_KEY=your-youtube-api-key

# Email (SMTP)
SMTP_SERVER=smtp.naver.com
SMTP_PORT=465
SMTP_USERNAME=your-email@naver.com
SMTP_PASSWORD=your-email-password
SMTP_FROM_EMAIL=your-email@naver.com

# Kafka (호스트 서버의 Kafka)
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_CLIENT_ID=facereview-api
KAFKA_GROUP_ID=facereview-consumer
KAFKA_TOPIC_USER_EVENT=user-event

# Logging
LOG_LEVEL=INFO
```

## 🛠️ 유용한 명령어

### 서비스 관리
```bash
# 모든 서비스 시작
docker-compose up -d

# 모든 서비스 중지
docker-compose stop

# 모든 서비스 재시작
docker-compose restart

# 특정 서비스만 재시작
docker-compose restart app

# 모든 서비스 중지 및 제거
docker-compose down
```

### 로그 확인
```bash
# 전체 로그 실시간 확인
docker-compose logs -f

# 특정 서비스 로그 확인
docker-compose logs -f app
docker-compose logs -f celery-worker
docker-compose logs -f kafka-consumer

# 최근 100줄만 확인
docker-compose logs --tail=100 app
```

### 서비스 상태 확인
```bash
# 실행 중인 서비스 확인
docker-compose ps

# 컨테이너 리소스 사용량
docker stats facereview-app
```

### 이미지 재빌드
```bash
# 캐시 없이 이미지 재빌드
docker-compose build --no-cache app

# 재빌드 후 재시작
docker-compose up -d --build
```

## 🔍 트러블슈팅

### 서비스가 시작되지 않는 경우
```bash
# 로그 확인
docker-compose logs app

# 컨테이너 재시작
docker-compose restart app
```

### DB 연결 실패
```bash
# MariaDB 연결 확인 (호스트에서)
mysql -h localhost -u facereview -p

# MongoDB 연결 확인 (호스트에서)
mongosh mongodb://localhost:27017

# Redis 연결 확인 (호스트에서)
redis-cli ping
```

### 포트 충돌
```bash
# 5000번 포트 사용 확인
sudo netstat -tlnp | grep :5000

# 프로세스 종료
sudo kill <PID>
```

### 디스크 공간 부족
```bash
# Docker 리소스 정리
docker system prune -a

# 로그 파일 정리
cd /home/winterholic/projects/services/new-facereview/logs
rm -f *.log.1 *.log.2
```

## 📊 Health Check

```bash
# 애플리케이션 헬스체크
curl http://localhost:5000/health

# 응답 예시
# {"status": "healthy", "service": "facereview"}
```

## 🔄 업데이트 및 롤백

### 업데이트
```bash
cd /home/winterholic/projects/services/new-facereview

# 코드 업데이트 (GitHub Actions가 자동으로 수행)
git pull origin main

# 재배포
./scripts/deploy.sh
```

### 롤백
```bash
# 이전 커밋으로 돌아가기
git checkout <previous-commit-hash>

# 재배포
./scripts/deploy.sh
```

## ⚙️ GitHub Secrets 설정

GitHub Repository → Settings → Secrets and variables → Actions에서 다음 Secret 추가:

```
# 서버 접속 정보
SERVER_HOST=your-server-ip
SERVER_USER=winterholic
SERVER_SSH_KEY=<your-private-key>
SERVER_PORT=22

# 애플리케이션 설정
FLASK_APP=run.py
FLASK_ENV=production
SECRET_KEY=<your-secret-key>
JWT_SECRET_KEY=<your-jwt-secret>

# 데이터베이스 (호스트 서버의 설정)
DB_USERNAME=facereview
DB_PASSWORD=<your-db-password>
DB_HOST=localhost
DB_PORT=3306
DB_NAME=facereview

# MongoDB (호스트 서버의 설정)
MONGO_HOST=localhost
MONGO_PORT=27017
MONGO_DB_NAME=facereview

# Redis (호스트 서버의 설정)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# 외부 서비스
YOUTUBE_API_KEY=<your-api-key>
SMTP_SERVER=smtp.naver.com
SMTP_PORT=465
SMTP_USERNAME=<your-email>
SMTP_PASSWORD=<your-password>
SMTP_FROM_EMAIL=<your-email>

# Kafka (호스트 서버의 설정)
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_CLIENT_ID=facereview-api
KAFKA_GROUP_ID=facereview-consumer
KAFKA_TOPIC_USER_EVENT=user-event
```

## 📝 배포 로그

배포 로그는 `logs/deploy.log` 파일에 기록됩니다.

```bash
# 최근 배포 로그 확인
tail -20 logs/deploy.log
```
