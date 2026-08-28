from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud
from app.auth import create_access_token, get_current_user, verify_password
from app.database import get_db
from app.google_auth import GoogleAuthNotConfigured, GoogleTokenInvalid, verify_google_id_token
from app.models import User
from app.schemas import GoogleLoginRequest, SnapshotOut, Token, UserCreate, UserLogin, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserOut, status_code=201)
def signup(user_in: UserCreate, db: Session = Depends(get_db)):
    if crud.get_user_by_username(db, user_in.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    return crud.create_user(db, user_in)


@router.post("/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, credentials.username)
    if not user or not user.password_hash or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {"access_token": create_access_token(user.id, user.is_kiosk)}


@router.post("/google-login", response_model=Token)
def google_login(payload: GoogleLoginRequest, db: Session = Depends(get_db)):
    try:
        claims = verify_google_id_token(payload.credential)
    except GoogleAuthNotConfigured:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")
    except GoogleTokenInvalid:
        raise HTTPException(status_code=401, detail="Invalid Google sign-in")

    email = claims.get("email")
    if not email or not claims.get("email_verified"):
        raise HTTPException(status_code=400, detail="Google account has no verified email")

    user = crud.get_user_by_email(db, email)
    if user is None:
        user = crud.create_google_user(db, email)
    return {"access_token": create_access_token(user.id, user.is_kiosk)}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/refresh", response_model=Token)
def refresh(current_user: User = Depends(get_current_user)):
    return {"access_token": create_access_token(current_user.id, current_user.is_kiosk)}


@router.post("/tour-seen", response_model=UserOut)
def mark_tour_seen(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Called once the welcome tour modal (DashboardPage.tsx) is dismissed,
    skipped, or finished - any of those count as "seen", so it never shows
    again for this account, on any device."""
    current_user.has_seen_tour = True
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/snapshots", response_model=list[SnapshotOut])
def get_snapshots(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    snaps = crud.get_user_snapshots(db, current_user.id)
    return [
        SnapshotOut(
            date=str(s.date),
            comic_count=s.comic_count,
            total_paid=s.total_paid,
            total_value=s.total_value,
        )
        for s in snaps
    ]
