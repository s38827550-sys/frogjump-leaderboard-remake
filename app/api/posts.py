import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field
from app.api.auth import get_current_user
from app.db.session import get_conn, release_conn

logger = logging.getLogger("FrogJump")
router = APIRouter(prefix="/posts", tags=["posts"])

class PostCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1)

class PostUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1)

class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)

# ── 글 목록 조회 ────────────────────────────────────────
@router.get("")
def get_posts(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100)
):
    offset = (page - 1) * size
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) as total FROM public.posts")
            total = cur.fetchone()["total"]

            cur.execute("""
                SELECT p.id, p.title, p.username, u.nickname,
                       p.created_at, p.updated_at,
                       COUNT(c.id) as comment_count
                FROM public.posts p
                JOIN public.users u ON p.username = u.username
                LEFT JOIN public.comments c ON p.id = c.post_id
                GROUP BY p.id, u.nickname
                ORDER BY p.created_at DESC
                LIMIT %s OFFSET %s
            """, (size, offset))
            rows = cur.fetchall()
        return {"total": total, "page": page, "size": size, "items": [dict(r) for r in rows]}
    except Exception as e:
        logger.error(f"Get posts error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get posts")
    finally:
        release_conn(conn)

# ── 글 상세 조회 ────────────────────────────────────────
@router.get("/{post_id}")
def get_post(post_id: int):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT p.id, p.title, p.content, p.username,
                       u.nickname, p.created_at, p.updated_at
                FROM public.posts p
                JOIN public.users u ON p.username = u.username
                WHERE p.id = %s
            """, (post_id,))
            post = cur.fetchone()
            if not post:
                raise HTTPException(status_code=404, detail="Post not found")

            cur.execute("""
                SELECT c.id, c.content, c.username,
                       u.nickname, c.created_at
                FROM public.comments c
                JOIN public.users u ON c.username = u.username
                WHERE c.post_id = %s
                ORDER BY c.created_at ASC
            """, (post_id,))
            comments = cur.fetchall()

        return {**dict(post), "comments": [dict(c) for c in comments]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get post error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get post")
    finally:
        release_conn(conn)

# ── 글 작성 ─────────────────────────────────────────────
@router.post("")
def create_post(body: PostCreate, username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO public.posts (username, title, content)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (username, body.title, body.content))
            post_id = cur.fetchone()["id"]
        conn.commit()
        return {"ok": True, "id": post_id}
    except Exception as e:
        conn.rollback()
        logger.error(f"Create post error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create post")
    finally:
        release_conn(conn)

# ── 글 수정 ─────────────────────────────────────────────
@router.patch("/{post_id}")
def update_post(post_id: int, body: PostUpdate, username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT username FROM public.posts WHERE id = %s", (post_id,))
            post = cur.fetchone()
            if not post:
                raise HTTPException(status_code=404, detail="Post not found")
            if post["username"] != username:
                raise HTTPException(status_code=403, detail="Not authorized")

            cur.execute("""
                UPDATE public.posts
                SET title = %s, content = %s, updated_at = NOW()
                WHERE id = %s
            """, (body.title, body.content, post_id))
        conn.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Update post error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update post")
    finally:
        release_conn(conn)

# ── 글 삭제 ─────────────────────────────────────────────
@router.delete("/{post_id}")
def delete_post(post_id: int, username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT username FROM public.posts WHERE id = %s", (post_id,))
            post = cur.fetchone()
            if not post:
                raise HTTPException(status_code=404, detail="Post not found")
            if post["username"] != username:
                raise HTTPException(status_code=403, detail="Not authorized")

            cur.execute("DELETE FROM public.posts WHERE id = %s", (post_id,))
        conn.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Delete post error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete post")
    finally:
        release_conn(conn)

# ── 댓글 작성 ───────────────────────────────────────────
@router.post("/{post_id}/comments")
def create_comment(post_id: int, body: CommentCreate, username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT 1 FROM public.posts WHERE id = %s", (post_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Post not found")

            cur.execute("""
                INSERT INTO public.comments (post_id, username, content)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (post_id, username, body.content))
            comment_id = cur.fetchone()["id"]
        conn.commit()
        return {"ok": True, "id": comment_id}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Create comment error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create comment")
    finally:
        release_conn(conn)

# ── 댓글 삭제 ───────────────────────────────────────────
@router.delete("/{post_id}/comments/{comment_id}")
def delete_comment(post_id: int, comment_id: int, username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT username FROM public.comments WHERE id = %s AND post_id = %s",
                       (comment_id, post_id))
            comment = cur.fetchone()
            if not comment:
                raise HTTPException(status_code=404, detail="Comment not found")
            if comment["username"] != username:
                raise HTTPException(status_code=403, detail="Not authorized")

            cur.execute("DELETE FROM public.comments WHERE id = %s", (comment_id,))
        conn.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Delete comment error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete comment")
    finally:
        release_conn(conn)