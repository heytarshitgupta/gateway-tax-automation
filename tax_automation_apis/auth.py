"""Session-based authentication and authorization helpers with HIGH-only context switching and effective permissions."""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
import models as m
import schemas as s

SESSION_COOKIE_NAME = "session_id"
SESSION_LIFETIME = timedelta(hours=12)

# In-memory session store: session_id -> {"staff_id": int, "selected_staff_id": int, "expires_at": datetime}
sessions: Dict[str, Dict[str, Any]] = {}


def create_session(staff_id: int) -> str:
    session_id = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    sessions[session_id] = {
        "staff_id": staff_id,
        "selected_staff_id": staff_id,
        "expires_at": now + SESSION_LIFETIME
    }
    return session_id


def get_session(session_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not session_id or session_id not in sessions:
        return None
    session_data = sessions[session_id]
    if datetime.now(timezone.utc) > session_data["expires_at"]:
        del sessions[session_id]
        return None
    return session_data


def get_session_staff_id(session_id: Optional[str]) -> Optional[int]:
    session = get_session(session_id)
    return session["staff_id"] if session else None


def get_session_selected_staff_id(session_id: Optional[str]) -> Optional[int]:
    session = get_session(session_id)
    if not session:
        return None
    return session.get("selected_staff_id", session["staff_id"])


def set_session_selected_staff_id(session_id: Optional[str], selected_id: int) -> None:
    session = get_session(session_id)
    if session:
        session["selected_staff_id"] = selected_id


def delete_session(session_id: Optional[str]) -> None:
    if session_id and session_id in sessions:
        del sessions[session_id]


def get_authenticated_staff(request: Request, db: Session = Depends(get_db)) -> m.Staff:
    """Retrieves the staff member who logged in with email and password."""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    staff_id = get_session_staff_id(session_id)
    if not staff_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    staff = db.get(m.Staff, staff_id)
    if not staff or not staff.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Staff account is inactive or not found"
        )
    return staff


def get_selected_staff(request: Request, db: Session = Depends(get_db)) -> m.Staff:
    """Retrieves the selected working staff context.
    
    For HIGH users: returns the currently selected staff member from session.
    For MEDIUM and LOW: always returns the authenticated staff member.
    """
    auth_staff = get_authenticated_staff(request, db)
    if auth_staff.access_level != m.AccessLevel.HIGH:
        return auth_staff

    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    selected_id = get_session_selected_staff_id(session_id)
    if not selected_id or selected_id == auth_staff.id:
        return auth_staff

    target = db.get(m.Staff, selected_id)
    if not target or not target.is_active:
        # Fall back to authenticated staff if target is missing or inactive
        set_session_selected_staff_id(session_id, auth_staff.id)
        return auth_staff
    return target


def get_effective_staff(request: Request, db: Session = Depends(get_db)) -> m.Staff:
    """Determines effective working staff for authorization and task ownership.
    
    - Normal LOW/MEDIUM login: effective staff is the authenticated staff.
    - Normal HIGH login: effective staff is the selected staff.
    """
    auth_staff = get_authenticated_staff(request, db)
    if auth_staff.access_level != m.AccessLevel.HIGH:
        return auth_staff
    return get_selected_staff(request, db)


def require_high_access(request: Request, db: Session = Depends(get_db)) -> m.Staff:
    """Authorizes operations requiring HIGH access level.
    
    Uses effective staff identity, ensuring that if a HIGH user selects a LOW
    or MEDIUM staff member, HIGH-only operations return 403 Forbidden.
    """
    effective = get_effective_staff(request, db)
    if effective.access_level != m.AccessLevel.HIGH:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation requires HIGH access level"
        )
    return effective


auth_router = APIRouter(prefix="/auth", tags=["Auth"])


@auth_router.post("/login", response_model=s.AuthMeResponse)
def login(data: s.LoginRequest, response: Response, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    staff = db.query(m.Staff).filter(func.lower(m.Staff.email) == email).first()
    # Generic error message to never reveal whether email exists or not
    if not staff or not staff.is_active or staff.password != data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    session_id = create_session(staff.id)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        path="/"
    )
    staff_out = s.StaffOut.model_validate(staff)
    return s.AuthMeResponse(
        **staff_out.model_dump(),
        selected_staff_id=staff.id,
        selected_staff=staff_out,
        effective_access_level=staff.access_level,
        is_authenticated_high=(staff.access_level == m.AccessLevel.HIGH)
    )


@auth_router.get("/me", response_model=s.AuthMeResponse)
def me(request: Request, db: Session = Depends(get_db)):
    auth_staff = get_authenticated_staff(request, db)
    selected_staff = get_selected_staff(request, db)
    effective_level = selected_staff.access_level if auth_staff.access_level == m.AccessLevel.HIGH else auth_staff.access_level
    return s.AuthMeResponse(
        **s.StaffOut.model_validate(auth_staff).model_dump(),
        selected_staff_id=selected_staff.id,
        selected_staff=s.StaffOut.model_validate(selected_staff),
        effective_access_level=effective_level,
        is_authenticated_high=(auth_staff.access_level == m.AccessLevel.HIGH)
    )


@auth_router.post("/select-context", response_model=s.AuthMeResponse)
def select_context(data: s.SwitchContextRequest, request: Request, db: Session = Depends(get_db)):
    # Crucial: uses get_authenticated_staff so HIGH user who selected LOW can always switch back
    auth_staff = get_authenticated_staff(request, db)
    if auth_staff.access_level != m.AccessLevel.HIGH:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Context switching requires HIGH access level"
        )

    target_staff = db.get(m.Staff, data.staff_id)
    if not target_staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target staff member not found"
        )
    if not target_staff.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot select an inactive staff member"
        )

    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    set_session_selected_staff_id(session_id, target_staff.id)

    return s.AuthMeResponse(
        **s.StaffOut.model_validate(auth_staff).model_dump(),
        selected_staff_id=target_staff.id,
        selected_staff=s.StaffOut.model_validate(target_staff),
        effective_access_level=target_staff.access_level,
        is_authenticated_high=True
    )


@auth_router.post("/logout")
def logout(request: Request, response: Response):
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    delete_session(session_id)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return {"status": "ok"}
