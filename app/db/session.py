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

    ssl_mode = "require" if "supabase" in url else "disable"

    connection_pool = pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=10,
        dsn=url,
        connect_timeout=10,
        sslmode=ssl_mode
    )

    logger.info(f"✅ Connection pool initialized. (sslmode={ssl_mode})")

def reset_pool():
    global connection_pool

    try:
        if connection_pool:
            connection_pool.closeall()
    except Exception:
        pass

    init_pool()
    logger.info("🔄 Connection pool reset")

def get_conn():
    if connection_pool is None:
        raise RuntimeError("Connection pool not initialized.")

    conn = connection_pool.getconn()

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception:
        logger.warning("⚠️ Dead connection detected. Resetting pool...")

        try:
            connection_pool.putconn(conn, close=True)
        except Exception:
            pass

        reset_pool()
        conn = connection_pool.getconn()

    return conn

def release_conn(conn):
    if connection_pool:
        connection_pool.putconn(conn)