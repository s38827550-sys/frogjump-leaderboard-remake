import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field
from app.api.auth import get_current_user
from app.db.session import get_conn, release_conn

logger = logging.getLogger("FrogJump")
router = APIRouter(prefix="/patch-notes", tags=["patch-notes"])

class PatchNoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1, max_length=20)

class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)

# ── 관리자 확인 ─────────────────────────────────────────
def check_admin(username: str, conn):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT role FROM public.users WHERE username = %s", (username,))
        user = cur.fetchone()
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

# ── 패치노트 목록 조회 ──────────────────────────────────
@router.get("")
def get_patch_notes(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100)
):
    offset = (page - 1) * size
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) as total FROM public.patch_notes")
            total = cur.fetchone()["total"]

            cur.execute("""
                SELECT p.id, p.title, p.version, p.username,
                       u.nickname, p.created_at,
                       COUNT(c.id) as comment_count
                FROM public.patch_notes p
                JOIN public.users u ON p.username = u.username
                LEFT JOIN public.patch_comments c ON p.id = c.patch_id
                GROUP BY p.id, u.nickname
                ORDER BY p.created_at DESC
                LIMIT %s OFFSET %s
            """, (size, offset))
            rows = cur.fetchall()
        return {"total": total, "page": page, "size": size, "items": [dict(r) for r in rows]}
    except Exception as e:
        logger.error(f"Get patch notes error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get patch notes")
    finally:
        release_conn(conn)

# ── 패치노트 상세 조회 ──────────────────────────────────
@router.get("/{patch_id}")
def get_patch_note(patch_id: int):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT p.id, p.title, p.content, p.version,
                       p.username, u.nickname, p.created_at
                FROM public.patch_notes p
                JOIN public.users u ON p.username = u.username
                WHERE p.id = %s
            """, (patch_id,))
            patch = cur.fetchone()
            if not patch:
                raise HTTPException(status_code=404, detail="Patch note not found")

            cur.execute("""
                SELECT c.id, c.content, c.username,
                       u.nickname, c.created_at
                FROM public.patch_comments c
                JOIN public.users u ON c.username = u.username
                WHERE c.patch_id = %s
                ORDER BY c.created_at ASC
            """, (patch_id,))
            comments = cur.fetchall()

        return {**dict(patch), "comments": [dict(c) for c in comments]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get patch note error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get patch note")
    finally:
        release_conn(conn)

# ── 패치노트 작성 (관리자만) ────────────────────────────
@router.post("")
def create_patch_note(body: PatchNoteCreate, username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        check_admin(username, conn)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO public.patch_notes (username, title, content, version)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (username, body.title, body.content, body.version))
            patch_id = cur.fetchone()["id"]
        conn.commit()
        return {"ok": True, "id": patch_id}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Create patch note error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create patch note")
    finally:
        release_conn(conn)

# ── 패치노트 삭제 (관리자만) ────────────────────────────
@router.delete("/{patch_id}")
def delete_patch_note(patch_id: int, username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        check_admin(username, conn)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT 1 FROM public.patch_notes WHERE id = %s", (patch_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Patch note not found")
            cur.execute("DELETE FROM public.patch_notes WHERE id = %s", (patch_id,))
        conn.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Delete patch note error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete patch note")
    finally:
        release_conn(conn)

# ── 댓글 작성 ───────────────────────────────────────────
@router.post("/{patch_id}/comments")
def create_comment(patch_id: int, body: CommentCreate, username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT 1 FROM public.patch_notes WHERE id = %s", (patch_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Patch note not found")

            cur.execute("""
                INSERT INTO public.patch_comments (patch_id, username, content)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (patch_id, username, body.content))
            comment_id = cur.fetchone()["id"]
        conn.commit()
        return {"ok": True, "id": comment_id}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Create patch comment error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create comment")
    finally:
        release_conn(conn)

# ── 댓글 삭제 ───────────────────────────────────────────
@router.delete("/{patch_id}/comments/{comment_id}")
def delete_comment(patch_id: int, comment_id: int, username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT c.username FROM public.patch_comments c
                JOIN public.users u ON c.username = u.username
                WHERE c.id = %s AND c.patch_id = %s
            """, (comment_id, patch_id))
            comment = cur.fetchone()
            if not comment:
                raise HTTPException(status_code=404, detail="Comment not found")

            # 본인 또는 관리자만 삭제 가능
            if comment["username"] != username:
                try:
                    check_admin(username, conn)
                except HTTPException:
                    raise HTTPException(status_code=403, detail="Not authorized")

            cur.execute("DELETE FROM public.patch_comments WHERE id = %s", (comment_id,))
        conn.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Delete patch comment error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete comment")
    finally:
        release_conn(conn)