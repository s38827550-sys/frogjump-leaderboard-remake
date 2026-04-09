# 🐸 FrogJump Leaderboard API

> **High-Performance, Scalable Game Backend Service**
> 
> 본 프로젝트는 실시간 게임 랭킹 시스템의 안정적인 운영을 위해 설계된 백엔드 서비스입니다. 
> 대규모 트래픽에서도 데이터 무결성을 보장하고, 효율적인 자원 관리를 위해 비동기 아키텍처와 최적화된 데이터베이스 레이어를 구축하는 데 집중했습니다.

[![CI](https://github.com/s38827550-sys/frogjump-leaderboard-remake/actions/workflows/ci.yml/badge.svg)](https://github.com/s38827550-sys/frogjump-leaderboard-remake/actions/workflows/ci.yml)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org)

---

## 🏗 System Architecture & Design

### 1. Asynchronous Task Handling (FastAPI)
- **FastAPI**의 비동기(ASGI) 지원을 활용하여 높은 I/O 동시성을 확보했습니다.
- 게임 클라이언트의 실시간 점수 제출 및 랭킹 조회 요청에 대해 최소한의 레이턴시로 응답합니다.

### 2. Database Layer Optimization
- **Connection Pooling**: `psycopg2.pool.ThreadedConnectionPool`을 사용하여 데이터베이스 커넥션 오버헤드를 줄이고 자원 사용을 최적화했습니다.
- **Indexing Strategy**: 랭킹 정렬 성능을 위해 `score DESC, updated_at ASC` 복합 인덱스를 적용하여 대량의 데이터셋에서도 `O(log N)` 수준의 빠른 조회 성능을 보장합니다.
- **Data Integrity**: `ON CONFLICT (username) DO UPDATE` (Upsert) 패턴을 사용하여 유저별 최고점 데이터를 원자적으로 관리합니다.

### 3. Security & Authentication
- **Stateless Auth**: 서버 확장성을 고려하여 **JWT (JSON Web Token)** 기반 인증 방식을 채택했습니다.
- **Security Best Practices**: `bcrypt` 라이브러리를 통해 패스워드를 안전하게 솔팅(Salting) 및 해싱하여 저장합니다.

### 4. Robust Infrastructure
- **Containerization**: Docker와 Docker Compose를 사용하여 개발 및 운영 환경의 일관성을 확보했습니다.
- **Dependency Management**: 서비스 간 의존성(Healthcheck)을 설정하여 데이터베이스가 완전히 준비된 상태에서만 API 서버가 구동되도록 설계했습니다.

---

## 📁 Project Structure

```text
app/
├── api/          # 비즈니스 로직 및 엔드포인트 라우팅
│   ├── auth.py      # 회원가입, JWT 로그인 처리
│   ├── scores.py    # 점수 등록 및 글로벌 랭킹 산출
│   └── users.py     # 유저 정보 및 프로필 관리
├── core/         # 전역 설정, 보안 정책, 공통 유틸리티
├── db/           # 데이터베이스 연결 및 커넥션 풀 라이프사이클 관리
├── models/       # Pydantic 데이터 검증 모델 및 DB 스키마
└── main.py       # 애플리케이션 엔트리포인트 및 미들웨어 설정
```

---

## 🛠 Engineering Decisions & Problem Solving

### Case 1. 복합 정렬 인덱싱을 통한 랭킹 조회 최적화
전체 랭킹 조회 시 점수(Score) 내림차순과 기록 갱신 시간(Updated_at) 오름차순이라는 두 가지 조건을 만족해야 합니다. 이를 위해 단순 인덱스가 아닌 복합 인덱스를 구성하여 데이터 정렬 비용을 사전에 제거, 데이터 증가에 따른 성능 저하 문제를 선제적으로 해결했습니다.

### Case 2. CI 파이프라인의 통합 테스트 자동화
코드 품질 유지를 위해 GitHub Actions CI 파이프라인에 통합 테스트를 구축했습니다. 테스트 실행 시 실제 운영 환경과 동일한 버전의 PostgreSQL 컨테이너를 Docker를 통해 실시간으로 기동하여, DB 레이어의 쿼리 동작까지 완벽하게 검증합니다.

### Case 3. bcrypt 호환성 및 종속성 관리
`passlib`과 최신 `bcrypt` 간의 호환성 문제를 해결하기 위해 의존성을 정밀하게 분석하여 `bcrypt==4.0.1`로 고정했습니다. 이는 단순 기능 구현을 넘어 시스템의 빌드 안정성을 확보하는 과정이었습니다.

---

## 🚀 Getting Started

### Prerequisites
- Docker & Docker Compose
- Or Python 3.12+ & PostgreSQL

### Execution with Docker
```bash
# 서비스 빌드 및 실행
docker-compose up --build -d

# 실행 확인
curl http://localhost:8000/health
```

### Manual Installation
```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🔗 Related Components
- **Client**: [FrogJump Game Client (Pygame)](https://github.com/s38827550-sys/FrogJumpGame)
- **Web UI**: [FrogJump Dashboard (React)](https://github.com/s38827550-sys/frogjump-web)
