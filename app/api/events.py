import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field
from datetime import datetime
from app.api.auth import get_current_user
from app.api.patch_notes import check_admin
from app.db.session import get_conn, release_conn

logger = logging.getLogger("FrogJump")
router = APIRouter(prefix="/events", tags=["events"])

class EventCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1)
    start_date: datetime
    end_date: datetime

# ── 이벤트 목록 조회 ────────────────────────────────────
@router.get("")
def get_events(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100)
):
    offset = (page - 1) * size
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) as total FROM public.events")
            total = cur.fetchone()["total"]

            cur.execute("""
                SELECT e.id, e.title, e.start_date, e.end_date,
                       e.username, u.nickname, e.created_at,
                       CASE
                           WHEN NOW() < e.start_date THEN '예정'
                           WHEN NOW() > e.end_date THEN '종료'
                           ELSE '진행중'
                       END as status
                FROM public.events e
                JOIN public.users u ON e.username = u.username
                ORDER BY e.created_at DESC
                LIMIT %s OFFSET %s
            """, (size, offset))
            rows = cur.fetchall()
        return {"total": total, "page": page, "size": size, "items": [dict(r) for r in rows]}
    except Exception as e:
        logger.error(f"Get events error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get events")
    finally:
        release_conn(conn)

# ── 이벤트 상세 조회 ────────────────────────────────────
@router.get("/{event_id}")
def get_event(event_id: int):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT e.id, e.title, e.content, e.start_date, e.end_date,
                       e.username, u.nickname, e.created_at,
                       CASE
                           WHEN NOW() < e.start_date THEN '예정'
                           WHEN NOW() > e.end_date THEN '종료'
                           ELSE '진행중'
                       END as status
                FROM public.events e
                JOIN public.users u ON e.username = u.username
                WHERE e.id = %s
            """, (event_id,))
            event = cur.fetchone()
            if not event:
                raise HTTPException(status_code=404, detail="Event not found")
        return dict(event)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get event error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get event")
    finally:
        release_conn(conn)

# ── 이벤트 작성 (관리자만) ──────────────────────────────
@router.post("")
def create_event(body: EventCreate, username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        check_admin(username, conn)
        if body.start_date >= body.end_date:
            raise HTTPException(status_code=400, detail="start_date must be before end_date")

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO public.events (username, title, content, start_date, end_date)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (username, body.title, body.content, body.start_date, body.end_date))
            event_id = cur.fetchone()["id"]
        conn.commit()
        return {"ok": True, "id": event_id}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Create event error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create event")
    finally:
        release_conn(conn)

# ── 이벤트 삭제 (관리자만) ──────────────────────────────
@router.delete("/{event_id}")
def delete_event(event_id: int, username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        check_admin(username, conn)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT 1 FROM public.events WHERE id = %s", (event_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Event not found")
            cur.execute("DELETE FROM public.events WHERE id = %s", (event_id,))
        conn.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Delete event error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete event")
    finally:
        release_conn(conn)