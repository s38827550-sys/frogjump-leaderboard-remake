import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import get_conn, release_conn

@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
    # 테스트 끝나면 test_ prefix 데이터 전부 삭제
    _cleanup()

def _cleanup():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.scores WHERE username LIKE 'test_%'")
            cur.execute("DELETE FROM public.users WHERE username LIKE 'test_%'")
        conn.commit()
        print("\n✅ Test data cleaned up.")
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Cleanup failed: {e}")
    finally:
        release_conn(conn)