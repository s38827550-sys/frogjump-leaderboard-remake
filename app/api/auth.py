import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from psycopg2.extras import RealDictCursor
from app.models.user import UserRegister, UserLogin, TokenResponse
from app.core.security import hash_password, verify_password, create_access_token, decode_token
from app.db.session import get_conn, release_conn

logger = logging.getLogger("FrogJump")
router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    try:
        return decode_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

@router.post("/signup")
def signup(body: UserRegister):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT 1 FROM public.users WHERE username = %s", (body.username,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Username already exists")
            
            cur.execute(
                "INSERT INTO public.users (username, password_hash) VALUES (%s, %s)",
                (body.username, hash_password(body.password))
            )
        conn.commit()
        return {"ok": True, "message": "Signup successful"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Signup error: {e}")
        raise HTTPException(status_code=500, detail="Signup failed")
    finally:
        release_conn(conn)

@router.post("/login", response_model=TokenResponse)
def login(body: UserLogin):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT username, password_hash FROM public.users WHERE username = %s",
                (body.username,)
            )
            user = cur.fetchone()
        
        if not user or not verify_password(body.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        return TokenResponse(access_token=create_access_token(user["username"]))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")
    finally:
        release_conn(conn)