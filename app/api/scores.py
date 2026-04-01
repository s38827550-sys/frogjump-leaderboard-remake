import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query
from psycopg2.extras import RealDictCursor
from app.models.score import ScoreIn, LeaderboardResponse, ScoreOut
from app.api.auth import get_current_user
from app.db.session import get_conn, release_conn

logger = logging.getLogger("FrogJump")
router = APIRouter(tags=["scores"])

@router.post("/scores")
def post_score(payload: ScoreIn, username: str = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO public.scores (username, score, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (username) DO UPDATE SET
                    score = CASE WHEN EXCLUDED.score > public.scores.score 
                                 THEN EXCLUDED.score ELSE public.scores.score END,
                    updated_at = CASE WHEN EXCLUDED.score > public.scores.score 
                                      THEN EXCLUDED.updated_at ELSE public.scores.updated_at END
                RETURNING score
            """, (username, payload.score, now))
            row = cur.fetchone()
        conn.commit()
        return {"ok": True, "best": int(row["score"])}
    except Exception as e:
        conn.rollback()
        logger.error(f"Post score error: {e}")
        raise HTTPException(status_code=500, detail="Failed to save score")
    finally:
        release_conn(conn)

@router.get("/leaderboard", response_model=LeaderboardResponse)
def get_leaderboard(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100)
):
    offset = (page - 1) * size
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) as total FROM public.scores")
            total = cur.fetchone()["total"]
            
            cur.execute("""
                SELECT 
                    ROW_NUMBER() OVER (ORDER BY score DESC, updated_at ASC) as rank,
                    username,
                    score
                FROM public.scores
                ORDER BY score DESC, updated_at ASC
                LIMIT %s OFFSET %s
            """, (size, offset))
            rows = cur.fetchall()
        
        return LeaderboardResponse(
            total=total,
            page=page,
            size=size,
            items=[ScoreOut(**r) for r in rows]
        )
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch leaderboard")
    finally:
        release_conn(conn)