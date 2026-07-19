<p align="center">
  <img src="./facereview-logo.svg" width="180" alt="FaceReview 로고" />
</p>

<h1 align="center">FaceReview</h1>

<p align="center">
  <strong>표정이 남긴 감정으로 다음 영상을 발견하는 비디오 추천 서비스</strong>
</p>

<table align="center">
  <thead>
    <tr>
      <th align="center">구분</th>
      <th align="center">URL</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td align="center">서비스</td>
      <td align="center"><a href="https://facereview.net">https://facereview.net</a></td>
    </tr>
    <tr>
      <td align="center">관리자</td>
      <td align="center"><a href="https://admin.facereview.net">https://admin.facereview.net</a></td>
    </tr>
    <tr>
      <td align="center">프로젝트 소개</td>
      <td align="center"><a href="https://portfolio.facereview.net">https://portfolio.facereview.net</a></td>
    </tr>
  </tbody>
</table>

<p align="center">2023.10 – 2023.12 · Team Project · 2026 Backend Refactoring</p>

---

## 프로젝트 소개

평점이 높아도 내게는 재미없고, 다른 사람의 혹평과 달리 의외로 재미있었던 경험에서 시작했습니다. 말로 남긴 리뷰만으로는 알기 어려운 취향을 **영상을 보는 순간의 감정**으로 이해할 수 있을지 고민했습니다.

FaceReview는 시청 중 표정을 감정 타임라인으로 만들고, 개인의 감정 기록과 영상별 반응을 연결해 다음 콘텐츠를 추천합니다. 접근하기 쉬운 YouTube 영상에서 시작했지만 영화·드라마·OTT 등 더 넓은 영상 경험으로 확장할 수 있도록 구상했습니다.

> **영상 발견 → 실시간 감정 분석 → 시청자 반응 비교 → 감정 기록 → 다음 영상 추천**

## 핵심 경험

### 1. 감정과 취향으로 영상을 발견합니다

최근 시청에서 쌓인 감정과 카테고리별 반응을 바탕으로 영상을 추천합니다. 개인화 추천뿐 아니라 카테고리, 검색, 즐겨찾기, 최신 영상 탐색도 함께 제공합니다.

#### 개인화 추천

<img src="./.github/readme-assets/service-personalized-feed.png" width="100%" alt="FaceReview 개인화 추천 화면" />

#### 카테고리별 추천

<img src="./.github/readme-assets/service-category-feed.png" width="100%" alt="FaceReview 카테고리별 추천 화면" />

### 2. 같은 순간의 감정을 함께 봅니다

웹캠 프레임을 5가지 감정으로 분석하고 영상 시점에 맞춰 기록합니다. 시청자는 자신의 현재 감정, 같은 순간 다른 시청자가 느낀 감정, 전체 영상의 감정 흐름을 한 화면에서 비교할 수 있습니다.

#### 실시간 감정 분석

<p align="center">
  <img src="./.github/readme-assets/tutorial-analysis.gif" width="720" alt="FaceReview 실시간 감정 분석" />
</p>

#### 시청 화면과 감정 타임라인

<img src="./.github/readme-assets/watch-overview.png" width="100%" alt="FaceReview 시청 화면과 감정 타임라인" />

### 3. 감정이 다음 추천으로 이어집니다

영상의 카테고리와 대표 감정을 기준으로 비슷한 반응을 이끌어낸 콘텐츠를 이어서 보여줍니다. 댓글과 연관 영상도 시청 흐름 안에서 함께 확인할 수 있습니다.

<img src="./.github/readme-assets/watch-related.png" width="100%" alt="FaceReview 댓글과 연관 영상 추천" />

### 4. 나의 감정 기록을 돌아봅니다

최근 본 영상마다 어떤 감정을 느꼈는지 타임라인으로 다시 확인하고, FaceReview를 이용하며 쌓인 감정 분포를 돌아볼 수 있습니다.

<img src="./.github/readme-assets/mypage-emotion-history.png" width="100%" alt="FaceReview 최근 시청 감정 히스토리" />

### 5. 서비스 운영 정보를 한곳에서 관리합니다

백오피스에서는 회원, 영상, 영상 등록 요청, 댓글을 관리하고 서비스 상태와 이용 지표를 확인합니다.

<img src="./.github/readme-assets/admin-dashboard.png" width="100%" alt="FaceReview 서비스 운영 백오피스" />

## 주요 기능

| 영역 | 제공 기능 |
|---|---|
| 영상 탐색 | 개인화 추천, 카테고리 추천, 검색, 즐겨찾기, 최신순 무한 스크롤 |
| 감정 분석 | 웹캠 프레임 기반 5가지 감정 분석과 실시간 표시 |
| 함께 보는 감정 | 나의 현재 감정, 같은 시점의 전체 시청자 감정, 영상 전체 타임라인 비교 |
| 연관 추천 | 같은 카테고리와 대표 감정을 가진 영상 추천 |
| 마이페이지 | 최근 시청 영상의 감정 타임라인과 누적 감정 분포 조회 |
| 백오피스 | 회원·영상·영상 등록 요청·댓글 관리와 서비스 현황 확인 |

## 기술 구성

| 영역 | 기술 |
|---|---|
| Frontend | React, TypeScript, Zustand, TanStack Query, SCSS |
| Backend | Flask, Flask-SocketIO, Celery, Celery Beat, Marshmallow |
| Emotion AI | TensorFlow, Keras, OpenCV |
| Data | MariaDB, MongoDB, Redis |
| External API | YouTube Data API |
| Infrastructure | Docker, Gunicorn, Cloudflare |

## 2026 리팩토링 주요 개선 내역

### 감정 데이터 집계와 추천 성능 개선

- 마이페이지 감정 요약을 전체 시청 세션 재계산 방식에서 **마지막 처리 시점 이후의 세션만 반영하는 증분 집계**로 전환했습니다.
- 체크포인트와 낙관적 락을 함께 사용해 동시 요청에서도 같은 세션이 중복 합산되지 않도록 했습니다.
- 실시간 감정 데이터의 수집·시청시간 계산 기준을 **2fps(0.5초 간격)** 로 통일하고, 표본이 30프레임 미만인 영상은 대표 감정을 확정하지 않습니다.
- 추천 점수를 30분마다 계산해 상위 1,000개 후보를 Redis에 저장하고, 요청 시에는 사용자 감정 벡터와의 유사도 계산에 집중하도록 분리했습니다.

### MariaDB–MongoDB 보상 트랜잭션

- 영상 승인·YouTube 영상 수집·테스트 데이터 생성처럼 두 데이터베이스를 함께 변경하는 작업에 **Saga 기반 보상 트랜잭션**을 적용했습니다.
- MongoDB 변경 전 상태를 보관하고 MariaDB 커밋 또는 후속 작업이 실패하면 등록된 보상 작업을 역순으로 실행해 신규 문서는 제거하고 기존 문서는 복원합니다.
- 배치 수집은 영상 1건 단위로 트랜잭션 경계를 분리해 한 건의 실패가 다른 영상 저장에 영향을 주지 않도록 했습니다.

### 비동기 작업과 운영 구조 정비

- 각 Gunicorn Worker가 예약 작업을 중복 실행할 수 있던 구조를 제거하고, **단일 Celery Beat 컨테이너**가 예약 작업을 발행하도록 분리했습니다.
- 웹·Celery Worker·Celery Beat를 독립 컨테이너로 운영하며, Celery 동시 실행 수를 제한해 TensorFlow 추론과 백그라운드 작업의 자원 경합을 줄였습니다.
- TensorFlow 모델을 로딩하는 Gunicorn Worker를 2개로 조정해 요청 처리 병렬성과 메모리 사용량 사이의 균형을 맞췄습니다.

### 운영 안전성과 회귀 검증

- 비활성 사용자 차단, Redis 토큰 블랙리스트, 운영 환경의 개발 전용 API 제외, 명시적 CORS Origin 등 인증·운영 경계를 정비했습니다.
- 인증, 추천, 2fps 집계, 증분 요약, Celery 구성, 보상 실패와 DB 커밋 실패 시나리오를 자동화 테스트로 검증합니다.

## 프로젝트 저장소

- **Frontend** — [`joowon-jang/facereview-front`](https://github.com/joowon-jang/facereview-front)
- **Backend** — [`winterholic/facereview-refactor-back`](https://github.com/winterholic/facereview-refactor-back)
- **Backoffice** — [`winterholic/new-facereview-admin-front`](https://github.com/winterholic/new-facereview-admin-front)
