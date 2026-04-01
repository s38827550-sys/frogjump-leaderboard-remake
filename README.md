# 🐸 FrogJump Leaderboard API

> 게임 클라이언트와 연동되는 백엔드 서버
> JWT 인증 기반 유저 시스템과 실시간 랭킹 API를 제공합니다.

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Render](https://img.shields.io/badge/Render-000000?style=flat&logo=render&logoColor=white)](https://render.com)

---

## 🔗 링크

- **API Server** → https://frogjump-leaderboard-remake.onrender.com
- **API Docs** → https://frogjump-leaderboard-remake.onrender.com/docs

---

## 🛠 기술 스택

![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Render](https://img.shields.io/badge/Render-000000?style=for-the-badge&logo=render&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)

---

## 📁 프로젝트 구조
```
app/
├── api/
│   ├── auth.py        # 회원가입 / 로그인
│   └── scores.py      # 점수 등록 / 랭킹 조회
├── core/
│   ├── config.py      # 환경변수 관리
│   └── security.py    # JWT / bcrypt
├── db/
│   └── session.py     # 커넥션 풀
├── models/
│   ├── user.py        # 유저 스키마
│   └── score.py       # 점수 스키마
└── main.py
```

---

## ⚙️ 주요 기능

| 기능 | 설명 |
|:---|:---|
| JWT 인증 | 로그인 시 토큰 발급, 인증된 유저만 점수 등록 가능 |
| bcrypt 해싱 | 비밀번호 단방향 암호화 저장 |
| 커넥션 풀 | ThreadedConnectionPool로 DB 커넥션 재사용 |
| Upsert | 동일 유저 점수 제출 시 최고점만 갱신 |
| 페이지네이션 | 랭킹 조회 시 page / size 파라미터 지원 |
| 인덱스 | score DESC 인덱스로 랭킹 조회 성능 최적화 |

---

## 🔌 API 명세

| Method | Endpoint | 설명 | 인증 |
|:---:|:---|:---|:---:|
| `POST` | `/auth/signup` | 회원가입 | ❌ |
| `POST` | `/auth/login` | 로그인 (JWT 발급) | ❌ |
| `POST` | `/scores` | 점수 등록 | ✅ |
| `GET` | `/leaderboard` | 랭킹 조회 | ❌ |
| `GET` | `/health` | 서버 상태 확인 | ❌ |

---

## 🧱 DB 설계
```sql
-- 유저 테이블
CREATE TABLE users (
    username      TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 점수 테이블
CREATE TABLE scores (
    username   TEXT PRIMARY KEY REFERENCES users(username),
    score      INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 랭킹 조회 성능을 위한 인덱스
CREATE INDEX idx_scores_score ON scores (score DESC, updated_at ASC);
```

---

## 💡 기술적 의사결정

**왜 FastAPI를 사용했는가?**
비동기 처리 지원과 Pydantic 기반 자동 유효성 검사, Swagger 자동 문서화로 개발 생산성을 높였습니다.

**왜 커넥션 풀인가?**
DB 커넥션 생성은 비용이 큰 작업입니다. 매 요청마다 새 커넥션을 열면 트래픽이 몰릴 때 병목이 생깁니다. ThreadedConnectionPool로 커넥션을 재사용해 성능을 개선했습니다.

**왜 JWT 방식을 넣었는가?**
세션 방식은 서버에 상태를 저장해야 하지만, JWT는 stateless라 서버 확장에 유리합니다. 토큰에서 유저 정보를 꺼내 쓰기 때문에 점수 등록 시 닉네임 위변조가 불가능합니다.

---

## 🐛 트러블슈팅

**bcrypt 버전 충돌**
passlib과 최신 bcrypt 버전이 호환되지 않는 문제 발생 → `bcrypt==4.0.1`로 버전 고정해 해결했습니다.

**Render 무료 인스턴스 sleep 문제**
15분 이상 요청이 없으면 서버가 잠듭니다. 실제 운영 환경이라면 keep-alive 요청이나 유료 인스턴스 전환을 적용할 것입니다.

---

## 🚀 로컬 실행
```bash
# 가상환경 생성 및 활성화
python -m venv .venv
.venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt

# 환경변수 설정 (.env 파일 생성)
DATABASE_URL=postgresql://...
SECRET_KEY=your_secret_key

# 서버 실행
uvicorn app.main:app --reload
```

---

## 🔗 관련 프로젝트

- [FrogJump Game Client](https://github.com/s38827550-sys/FrogJumpGame) — Python/Pygame 게임 클라이언트
- [FrogJump Web](https://github.com/s38827550-sys/frogjump-web) — React 웹 프론트엔드