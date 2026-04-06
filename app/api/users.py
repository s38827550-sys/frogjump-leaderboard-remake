import logging
from datetime import date, datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field
from app.api.auth import get_current_user
from app.db.session import get_conn, release_conn

logger = logging.getLogger("FrogJump")
router = APIRouter(prefix="/users", tags=["users"])

class NicknameUpdate(BaseModel):
    nickname: str = Field(..., min_length=2, max_length=16)

# ── 내 프로필 조회 ──────────────────────────────────────
@router.get("/me")
def get_my_profile(username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT username, nickname, points, last_attendance, created_at, role, status
                FROM public.users
                WHERE username = %s
            """, (username,))
            user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return dict(user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get profile error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get profile")
    finally:
        release_conn(conn)

# ── 닉네임 변경 (100포인트 차감) ───────────────────────
@router.patch("/me/nickname")
def update_nickname(body: NicknameUpdate, username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT nickname, points FROM public.users WHERE username = %s", (username,))
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            if user["points"] < 100:
                raise HTTPException(status_code=400, detail="Not enough points (100 required)")
            if user["nickname"] == body.nickname:
                raise HTTPException(status_code=400, detail="Same as current nickname")

            # 닉네임 중복 확인
            cur.execute("SELECT 1 FROM public.users WHERE nickname = %s AND username != %s",
                       (body.nickname, username))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Nickname already exists")

            cur.execute("""
                UPDATE public.users
                SET nickname = %s, points = points - 100
                WHERE username = %s
            """, (body.nickname, username))

            # 포인트 로그
            cur.execute("""
                INSERT INTO public.point_logs (username, points, reason)
                VALUES (%s, %s, %s)
            """, (username, -100, "닉네임 변경"))

        conn.commit()
        return {"ok": True, "message": "Nickname updated"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Update nickname error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update nickname")
    finally:
        release_conn(conn)

# ── 출석체크 ────────────────────────────────────────────
@router.post("/me/attendance")
def attendance(username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        today = date.today()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT last_attendance, points FROM public.users WHERE username = %s", (username,))
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            if user["last_attendance"] and user["last_attendance"] == today:
                raise HTTPException(status_code=400, detail="Already attended today")

            cur.execute("""
                UPDATE public.users
                SET last_attendance = %s, points = points + 3
                WHERE username = %s
            """, (today, username))

            cur.execute("""
                INSERT INTO public.point_logs (username, points, reason)
                VALUES (%s, %s, %s)
            """, (username, 3, "출석체크"))

        conn.commit()
        return {"ok": True, "message": "Attendance checked", "points_earned": 3}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Attendance error: {e}")
        raise HTTPException(status_code=500, detail="Failed to check attendance")
    finally:
        release_conn(conn)

# ── 회원탈퇴 ────────────────────────────────────────────
@router.delete("/me")
def delete_account(username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                UPDATE public.users
                SET status = 'deleted', deleted_at = %s
                WHERE username = %s
            """, (datetime.now(timezone.utc), username))
        conn.commit()
        return {"ok": True, "message": "Account deleted"}
    except Exception as e:
        conn.rollback()
        logger.error(f"Delete account error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete account")
    finally:
        release_conn(conn)

# ── 접속유저 등록/갱신 ──────────────────────────────────
@router.post("/online")
def update_online(username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.online_users (username, last_seen)
                VALUES (%s, %s)
                ON CONFLICT (username) DO UPDATE SET last_seen = EXCLUDED.last_seen
            """, (username, datetime.now(timezone.utc)))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        logger.error(f"Update online error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update online status")
    finally:
        release_conn(conn)

# ── 접속유저 목록 조회 ──────────────────────────────────
@router.get("/online")
def get_online_users():
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT u.username, u.nickname, o.last_seen
                FROM public.online_users o
                JOIN public.users u ON o.username = u.username
                WHERE o.last_seen > NOW() - INTERVAL '5 minutes'
                ORDER BY o.last_seen DESC
            """)
            rows = cur.fetchall()
        return {"total": len(rows), "users": [dict(r) for r in rows]}
    except Exception as e:
        logger.error(f"Get online users error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get online users")
    finally:
        release_conn(conn)

# ── 로그아웃 (접속유저에서 제거) ────────────────────────
@router.delete("/online")
def go_offline(username: str = Depends(get_current_user)):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.online_users WHERE username = %s", (username,))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        logger.error(f"Go offline error: {e}")
        raise HTTPException(status_code=500, detail="Failed to go offline")
    finally:
        release_conn(conn)