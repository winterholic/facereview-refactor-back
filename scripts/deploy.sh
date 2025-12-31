#!/bin/bash

# FaceReview Docker 무중단 배포 스크립트
# Blue-Green Deployment 방식

set -e

APP_NAME="facereview"
APP_DIR="/home/ubuntu/facereview"
DOCKER_IMAGE="facereview-app"

# 색상 정의
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# 현재 실행 중인 컨테이너 확인
CURRENT_CONTAINER=$(cat $APP_DIR/.current_container 2>/dev/null || echo "blue")

# 다음 배포 컨테이너 결정 (Blue-Green 전환)
if [ "$CURRENT_CONTAINER" == "blue" ]; then
    NEXT_CONTAINER="green"
    NEXT_PORT=8002
    CURRENT_PORT=8001
else
    NEXT_CONTAINER="blue"
    NEXT_PORT=8001
    CURRENT_PORT=8002
fi

CURRENT_NAME="${APP_NAME}-${CURRENT_CONTAINER}"
NEXT_NAME="${APP_NAME}-${NEXT_CONTAINER}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  FaceReview 무중단 배포 시작${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "현재 컨테이너: ${GREEN}$CURRENT_NAME${NC} (포트: $CURRENT_PORT)"
echo -e "배포 컨테이너: ${GREEN}$NEXT_NAME${NC} (포트: $NEXT_PORT)"
echo ""

# .env 파일 확인
if [ -f "$APP_DIR/.env" ]; then
    echo -e "${GREEN}✓${NC} .env 파일 확인됨"
else
    echo -e "${RED}✗${NC} .env 파일이 없습니다!"
    exit 1
fi

# 로그 디렉토리 생성
mkdir -p $APP_DIR/logs

# 새 컨테이너 시작
echo -e "\n${BLUE}[1/5]${NC} 새 컨테이너 시작 중... ($NEXT_NAME)"

# 기존 중지된 컨테이너가 있으면 삭제
docker rm -f $NEXT_NAME 2>/dev/null || true

# 새 Docker 컨테이너 실행
docker run -d \
    --name $NEXT_NAME \
    --network host \
    --env-file $APP_DIR/.env \
    -v $APP_DIR/logs:/app/logs \
    --restart unless-stopped \
    -e PORT=$NEXT_PORT \
    $DOCKER_IMAGE:latest

sleep 5

# 새 컨테이너 헬스체크
echo -e "\n${BLUE}[2/5]${NC} 헬스체크 진행 중..."
HEALTH_CHECK_URL="http://127.0.0.1:$NEXT_PORT/health"
MAX_RETRIES=15
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_CHECK_URL || echo "000")

    if [ "$HTTP_CODE" == "200" ]; then
        echo -e "${GREEN}✓${NC} 헬스체크 성공 (HTTP $HTTP_CODE)"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo -e "  시도 $RETRY_COUNT/$MAX_RETRIES - 응답 코드: $HTTP_CODE"

        if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
            echo -e "${RED}✗${NC} 헬스체크 실패! 배포를 중단합니다."
            # 컨테이너 로그 출력
            echo -e "\n${RED}컨테이너 로그:${NC}"
            docker logs $NEXT_NAME --tail 50
            # 새로 시작한 컨테이너 중지 및 삭제
            docker stop $NEXT_NAME 2>/dev/null || true
            docker rm $NEXT_NAME 2>/dev/null || true
            exit 1
        fi
        sleep 3
    fi
done

# Nginx upstream 전환
echo -e "\n${BLUE}[3/5]${NC} Nginx upstream 전환 중..."

# Nginx upstream 설정 업데이트
sudo tee /etc/nginx/conf.d/facereview_upstream.conf > /dev/null <<EOF
upstream facereview_backend {
    server 127.0.0.1:$NEXT_PORT;
}
EOF

# Nginx 설정 테스트
if sudo nginx -t > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Nginx 설정 검증 완료"
else
    echo -e "${RED}✗${NC} Nginx 설정 오류!"
    docker stop $NEXT_NAME 2>/dev/null || true
    docker rm $NEXT_NAME 2>/dev/null || true
    exit 1
fi

# Nginx reload
sudo systemctl reload nginx
echo -e "${GREEN}✓${NC} Nginx 리로드 완료"

sleep 2

# 이전 컨테이너 종료
echo -e "\n${BLUE}[4/5]${NC} 이전 컨테이너 종료 중... ($CURRENT_NAME)"

if docker ps -a --format '{{.Names}}' | grep -q "^${CURRENT_NAME}$"; then
    # Graceful shutdown (최대 30초 대기)
    docker stop -t 30 $CURRENT_NAME 2>/dev/null || true

    # 컨테이너 삭제
    docker rm $CURRENT_NAME 2>/dev/null || true

    echo -e "${GREEN}✓${NC} 이전 컨테이너 정상 종료됨"
else
    echo -e "  이전 컨테이너 없음 (첫 배포)"
fi

# 현재 컨테이너 정보 저장
echo $NEXT_CONTAINER > $APP_DIR/.current_container

# 배포 정보 기록
echo -e "\n${BLUE}[5/5]${NC} 배포 정보 기록 중..."
DEPLOY_LOG="$APP_DIR/logs/deploy.log"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Deployed to $NEXT_NAME (port: $NEXT_PORT)" >> $DEPLOY_LOG

# 완료
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  배포 완료!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "활성 컨테이너: ${GREEN}$NEXT_NAME${NC} (포트: $NEXT_PORT)"
echo -e "배포 시간: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 컨테이너 상태 확인
echo -e "${BLUE}현재 실행 중인 컨테이너:${NC}"
docker ps --filter "name=${APP_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

exit 0
