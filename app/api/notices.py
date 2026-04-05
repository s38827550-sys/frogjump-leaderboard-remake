import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field
from typing import Optional
from app.api.auth import get_current_user
from app.api.patch_notes import check_admin
from app.db.session import get_conn, release_conn

logger = logging.getLogger("FrogJump")
router = APIRouter(prefix="/notices", tags=["notices"])

class NoticeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1)
    importance: str = Field("normal", pattern="^(normal|important|urgent)$")
    is_pinned: bool = False

class ReactionCreate(BaseModel):
    reaction: str = Field(..., pattern="^(like|dislike)$")

# ── 공지사항 목록 조회 ──────────────────────────────────
@router.get("")
def get_notices(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100)
):
    offset = (page - 1) * size
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) as total FROM public.notices")
            total = cur.fetchone()["total"]

            cur.execute("""
                SELECT n.id, n.title, n.importance, n.is_pinned,
                       n.username, u.nickname, n.created_at
                FROM public.notices n
                JOIN public.users u ON n.username = u.username
                ORDER BY n.is_pinned DESC, n.created_at DESC
                LIMIT %s OFFSET %s
            """, (size, offset))
            rows = cur.fetchall()
        return {"total": total, "page": page, "size": size, "items": [dict(r) for r in rows]}
    except Exception as e:
        logger.error(f"Get notices error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get notices")
    finally:
        release_conn(conn)

# ── 공지사항 상세 조회 ──────────────────────────────────
@router.get("/{notice_id}")
def get_notice(notice_id: int):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT n.id, n.title, n.content, n.importance,
                       n.is_pinned, n.username, u.nickname, n.created_at,
                       COUNT(CASE WHEN r.reaction = 'like' THEN 1 END) as likes,
                       COUNT(CASE WHEN r.reaction = 'dislike' THEN 1 END) as dislikes
                FROM public.notices n
                JOIN public.users u ON n.username = u.username
                LEFT JOIN public.notice_reactions r ON n.id = r.notice_id
                WHERE n.id = %s
                GROUP BY n.id, u.nickname
            """, (notice_id,))
            notice = cur.fetchone()
            if not notice:
                raise HTTPException(status_code=404, detail="Notice not found")
        return dict(notice)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get notice error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get notice")
    finally:
        release_conn(conn)

# ── 공지사항 작성 (관리자만) ────────────────────────────
@router.post("")
def create_notice(body: NoticeCreate, username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        check_admin(username, conn)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO public.notices (username, title, content, importance, is_pinned)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (username, body.title, body.content, body.importance, body.is_pinned))
            notice_id = cur.fetchone()["id"]
        conn.commit()
        return {"ok": True, "id": notice_id}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Create notice error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create notice")
    finally:
        release_conn(conn)

# ── 공지사항 삭제 (관리자만) ────────────────────────────
@router.delete("/{notice_id}")
def delete_notice(notice_id: int, username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        check_admin(username, conn)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT 1 FROM public.notices WHERE id = %s", (notice_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Notice not found")
            cur.execute("DELETE FROM public.notices WHERE id = %s", (notice_id,))
        conn.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Delete notice error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete notice")
    finally:
        release_conn(conn)

# ── 좋아요/싫어요 ────────────────────────────────────────
@router.post("/{notice_id}/reactions")
def react_notice(notice_id: int, body: ReactionCreate, username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT 1 FROM public.notices WHERE id = %s", (notice_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Notice not found")

            # 이미 같은 반응이면 취소 (토글)
            cur.execute("""
                SELECT reaction FROM public.notice_reactions
                WHERE notice_id = %s AND username = %s
            """, (notice_id, username))
            existing = cur.fetchone()

            if existing and existing["reaction"] == body.reaction:
                cur.execute("""
                    DELETE FROM public.notice_reactions
                    WHERE notice_id = %s AND username = %s
                """, (notice_id, username))
            else:
                cur.execute("""
                    INSERT INTO public.notice_reactions (notice_id, username, reaction)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (notice_id, username) DO UPDATE SET reaction = EXCLUDED.reaction
                """, (notice_id, username, body.reaction))

        conn.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"React notice error: {e}")
        raise HTTPException(status_code=500, detail="Failed to react")
    finally:
        release_conn(conn)