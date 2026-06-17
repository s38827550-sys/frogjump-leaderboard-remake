import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from app.db.session import init_pool, connection_pool, get_conn, release_conn
from app.api import auth, scores, users, posts, patch_notes, notices, events, inquiries
from psycopg2.extras import RealDictCursor
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from app.core.security import decode_token  # decode_token 대신 기존 함수 재활용

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FrogJump")

def init_db():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    nickname TEXT UNIQUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.scores (
                    username TEXT PRIMARY KEY REFERENCES public.users(username) ON DELETE CASCADE,
                    score INTEGER NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_scores_score 
                ON public.scores (score DESC, updated_at ASC)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.online_users (
                    username TEXT PRIMARY KEY REFERENCES public.users(username) ON DELETE CASCADE,
                    last_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_online_users_last_seen
                ON public.online_users(last_seen DESC)
            """)
        conn.commit()
        logger.info("✅ Tables initialized.")
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ DB init failed: {e}")
    finally:
        release_conn(conn)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pool()
    init_db()
    yield
    if connection_pool:
        connection_pool.closeall()
        logger.info("🔒 Connection pool closed.")

app = FastAPI(title="FrogJump API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://frogjump-web.vercel.app", "http://localhost:3000", ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(scores.router)
app.include_router(users.router)
app.include_router(posts.router)
app.include_router(patch_notes.router)
app.include_router(notices.router)
app.include_router(events.router)
app.include_router(inquiries.router)

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

@app.get("/health")
async def health():
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT 1")
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})
    finally:
        release_conn(conn)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"🚨 Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Critical server error"})

@app.websocket("/ws/online")
async def ws_online(websocket: WebSocket, token: str):
    # 토큰 검증
    try:
        username = decode_token(token)
    except Exception:
        await websocket.close(code=4001)
        return

    await websocket.accept()

    # 연결 시 접속유저 등록
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.online_users (username, last_seen)
                VALUES (%s, NOW())
                ON CONFLICT (username) DO UPDATE SET last_seen = NOW()
            """, (username,))
        conn.commit()
    finally:
        release_conn(conn)

    try:
        while True:
            conn = get_conn()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT u.username, u.nickname, 
                            to_char(o.last_seen AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD HH24:MI:SS') as last_seen
                        FROM public.online_users o
                        JOIN public.users u ON o.username = u.username
                        WHERE o.last_seen > NOW() - INTERVAL '5 minutes'
                        ORDER BY o.last_seen DESC
                    """)
                    rows = [dict(r) for r in cur.fetchall()]
            finally:
                release_conn(conn)

            await websocket.send_json({"users": rows})
            await asyncio.sleep(5)

    except WebSocketDisconnect:
        # 연결 끊기면 접속유저에서 제거
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM public.online_users WHERE username = %s",
                    (username,)
                )
            conn.commit()
        finally:
            release_conn(conn)