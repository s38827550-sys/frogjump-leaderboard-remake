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
    
    connection_pool = pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=10,
        dsn=url,
        connect_timeout=10,
        sslmode='require'
    )
    logger.info("✅ Connection pool initialized.")

def get_conn():
    if connection_pool is None:
        raise RuntimeError("Connection pool not initialized.")
    return connection_pool.getconn()

def release_conn(conn):
    if connection_pool:
        connection_pool.putconn(conn)