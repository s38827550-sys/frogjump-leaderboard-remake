from psycopg2 import pool
from app.core.config import settings
import logging

logger = logging.getLogger("FrogJump")

connection_pool = None

def init_pool():
    global connection_pool
    url = settings.DATABASE_URL

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    # 🔥 핵심: 환경별 sslmode 분기
    if "localhost" in url or "127.0.0.1" in url:
        ssl_mode = "disable"
    else:
        ssl_mode = "require"

    connection_pool = pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=10,
        dsn=url,
        connect_timeout=10,
        sslmode=ssl_mode
    )

    logger.info(f"✅ Connection pool initialized. (sslmode={ssl_mode})")

def get_conn():
    if connection_pool is None:
        raise RuntimeError("Connection pool not initialized.")
    return connection_pool.getconn()

def release_conn(conn):
    if connection_pool:
        connection_pool.putconn(conn)