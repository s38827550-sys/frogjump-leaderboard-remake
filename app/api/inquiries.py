import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field
from typing import Optional
from app.api.auth import get_current_user
from app.api.patch_notes import check_admin
from app.db.session import get_conn, release_conn

logger = logging.getLogger("FrogJump")
router = APIRouter(prefix="/inquiries", tags=["inquiries"])

class InquiryCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1)

class InquiryAnswer(BaseModel):
    answer: str = Field(..., min_length=1)

class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)

# ── 문의 목록 조회 ──────────────────────────────────────
@router.get("")
def get_inquiries(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    username: str = Depends(get_current_user)
):
    offset = (page - 1) * size
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 관리자면 전체, 일반 유저면 본인 것만
            cur.execute("SELECT role FROM public.users WHERE username = %s", (username,))
            user = cur.fetchone()
            is_admin = user and user.get("role") == "admin"

            if is_admin:
                cur.execute("SELECT COUNT(*) as total FROM public.inquiries")
                total = cur.fetchone()["total"]
                cur.execute("""
                    SELECT i.id, i.title, i.status, i.username,
                           u.nickname, i.created_at
                    FROM public.inquiries i
                    JOIN public.users u ON i.username = u.username
                    ORDER BY i.created_at DESC
                    LIMIT %s OFFSET %s
                """, (size, offset))
            else:
                cur.execute("""
                    SELECT COUNT(*) as total FROM public.inquiries
                    WHERE username = %s
                """, (username,))
                total = cur.fetchone()["total"]
                cur.execute("""
                    SELECT i.id, i.title, i.status, i.username,
                           u.nickname, i.created_at
                    FROM public.inquiries i
                    JOIN public.users u ON i.username = u.username
                    WHERE i.username = %s
                    ORDER BY i.created_at DESC
                    LIMIT %s OFFSET %s
                """, (username, size, offset))

            rows = cur.fetchall()
        return {"total": total, "page": page, "size": size, "items": [dict(r) for r in rows]}
    except Exception as e:
        logger.error(f"Get inquiries error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get inquiries")
    finally:
        release_conn(conn)

# ── 문의 상세 조회 ──────────────────────────────────────
@router.get("/{inquiry_id}")
def get_inquiry(inquiry_id: int, username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT role FROM public.users WHERE username = %s", (username,))
            user = cur.fetchone()
            is_admin = user and user.get("role") == "admin"

            cur.execute("""
                SELECT i.id, i.title, i.content, i.answer,
                       i.status, i.username, u.nickname,
                       i.created_at, i.answered_at
                FROM public.inquiries i
                JOIN public.users u ON i.username = u.username
                WHERE i.id = %s
            """, (inquiry_id,))
            inquiry = cur.fetchone()

            if not inquiry:
                raise HTTPException(status_code=404, detail="Inquiry not found")
            if not is_admin and inquiry["username"] != username:
                raise HTTPException(status_code=403, detail="Not authorized")

        return dict(inquiry)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get inquiry error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get inquiry")
    finally:
        release_conn(conn)

# ── 문의 작성 ───────────────────────────────────────────
@router.post("")
def create_inquiry(body: InquiryCreate, username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO public.inquiries (username, title, content)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (username, body.title, body.content))
            inquiry_id = cur.fetchone()["id"]
        conn.commit()
        return {"ok": True, "id": inquiry_id}
    except Exception as e:
        conn.rollback()
        logger.error(f"Create inquiry error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create inquiry")
    finally:
        release_conn(conn)

# ── 문의 답변 (관리자만) ────────────────────────────────
@router.patch("/{inquiry_id}/answer")
def answer_inquiry(inquiry_id: int, body: InquiryAnswer, username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        check_admin(username, conn)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT 1 FROM public.inquiries WHERE id = %s", (inquiry_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Inquiry not found")

            cur.execute("""
                UPDATE public.inquiries
                SET answer = %s, status = '답변완료', answered_at = NOW()
                WHERE id = %s
            """, (body.answer, inquiry_id))
        conn.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Answer inquiry error: {e}")
        raise HTTPException(status_code=500, detail="Failed to answer inquiry")
    finally:
        release_conn(conn)

# ── 문의 삭제 ───────────────────────────────────────────
@router.delete("/{inquiry_id}")
def delete_inquiry(inquiry_id: int, username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT username FROM public.inquiries WHERE id = %s", (inquiry_id,))
            inquiry = cur.fetchone()
            if not inquiry:
                raise HTTPException(status_code=404, detail="Inquiry not found")

            # 본인 또는 관리자만 삭제 가능
            if inquiry["username"] != username:
                try:
                    check_admin(username, conn)
                except HTTPException:
                    raise HTTPException(status_code=403, detail="Not authorized")

            cur.execute("DELETE FROM public.inquiries WHERE id = %s", (inquiry_id,))
        conn.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Delete inquiry error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete inquiry")
    finally:
        release_conn(conn)

# ── 1:1 채팅 메시지 추가 ────────────────────────────────
@router.post("/{inquiry_id}/chat")
def add_chat(inquiry_id: int, body: ChatMessage, username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT username, status FROM public.inquiries WHERE id = %s", (inquiry_id,))
            inquiry = cur.fetchone()
            if not inquiry:
                raise HTTPException(status_code=404, detail="Inquiry not found")

            cur.execute("SELECT role FROM public.users WHERE username = %s", (username,))
            user = cur.fetchone()
            is_admin = user and user.get("role") == "admin"

            if not is_admin and inquiry["username"] != username:
                raise HTTPException(status_code=403, detail="Not authorized")

            is_admin_msg = is_admin
            cur.execute("""
                UPDATE public.inquiries
                SET answer = COALESCE(answer, '') || %s,
                    status = CASE WHEN %s THEN '답변완료' ELSE status END,
                    answered_at = CASE WHEN %s THEN NOW() ELSE answered_at END
                WHERE id = %s
            """, (
                f"\n[{'관리자' if is_admin_msg else '유저'}] {body.message}",
                is_admin_msg, is_admin_msg,
                inquiry_id
            ))
        conn.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Add chat error: {e}")
        raise HTTPException(status_code=500, detail="Failed to add chat message")
    finally:
        release_conn(conn)