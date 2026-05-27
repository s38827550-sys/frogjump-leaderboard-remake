from psycopg2 import pool
from psycopg2 import OperationalError, InterfaceError
from app.core.config import settings
import logging

logger = logging.getLogger("FrogJump")

connection_pool = None

def init_pool():
    global connection_pool

    if connection_pool is not None:
        return

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


def get_conn():
    global connection_pool

    if connection_pool is None:
        init_pool()

    try:
        conn = connection_pool.getconn()

        with conn.cursor() as cur:
            cur.execute("SELECT 1")

        return conn

    except (OperationalError, InterfaceError) as e:
        logger.error(f"❌ DB connection error: {e}")

        # 죽은 커넥션만 폐기
        try:
            connection_pool.putconn(conn, close=True)
        except (OperationalError, InterfaceError):
            pass

        # 새 커넥션 재시도
        conn = connection_pool.getconn()

        return conn


def release_conn(conn):
    global connection_pool

    if connection_pool and conn:
        connection_pool.putconn(conn)