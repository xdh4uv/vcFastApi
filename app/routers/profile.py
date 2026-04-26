from datetime import date
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..core.config import settings
from ..utils.country_codes import COUNTRY_CODES
from ..core.database import get_db
from ..models import usersModel as User
from ..schemas.schemas import OnboardingIn, ProfileOut, ProfileUpdate
from ..core.security import get_current_user

router = APIRouter(prefix="/profile", tags=["profile"])

UPLOAD_DIR = Path(settings.uploads_dir) / "avatars"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_MIME = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
MAX_AVATAR_BYTES = 2 * 1024 * 1024


def _calc_age(dob: date) -> int:
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _compute_initials(user: User) -> str:
    source = (user.full_name or user.username or user.email or "").strip()
    parts = [p for p in source.replace("_", " ").replace("-", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _to_out(user: User) -> ProfileOut:
    return ProfileOut(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        date_of_birth=user.date_of_birth,
        age=_calc_age(user.date_of_birth) if user.date_of_birth else None,
        gender=user.gender,
        bio=user.bio,
        phone_country_code=user.phone_country_code,
        phone_number=user.phone_number,
        avatar_url=user.avatar_url,
        initials=_compute_initials(user),
        onboarding_completed=user.onboarding_completed,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _delete_prior_avatar(user: User) -> None:
    if not user.avatar_url:
        return
    prev = UPLOAD_DIR / Path(user.avatar_url).name
    if prev.exists() and prev.name.startswith(f"{user.id}_"):
        prev.unlink(missing_ok=True)


@router.get("/country-codes")
def country_codes() -> list[dict]:
    return COUNTRY_CODES


@router.get("/me", response_model=ProfileOut)
def get_me(user: User = Depends(get_current_user)) -> ProfileOut:
    return _to_out(user)


@router.post(
    "/onboarding",
    response_model=ProfileOut,
    status_code=status.HTTP_200_OK,
)
def complete_onboarding(
    payload: OnboardingIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProfileOut:
    if user.onboarding_completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Onboarding already completed; use PATCH /profile/me",
        )
    user.full_name = payload.full_name
    user.date_of_birth = payload.date_of_birth
    user.gender = payload.gender
    user.bio = payload.bio
    user.phone_country_code = payload.phone_country_code
    user.phone_number = payload.phone_number
    user.onboarding_completed = True
    db.commit()
    db.refresh(user)
    return _to_out(user)


@router.patch("/me", response_model=ProfileOut)
def update_me(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProfileOut:
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    new_username = data.get("username")
    if new_username and new_username != user.username:
        clash = (
            db.query(User)
            .filter(User.username == new_username, User.id != user.id)
            .first()
        )
        if clash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken",
            )
    for key, value in data.items():
        setattr(user, key, value)

    final_cc = user.phone_country_code
    final_num = user.phone_number
    if bool(final_cc) != bool(final_num):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="phone_country_code and phone_number must be set together",
        )

    db.commit()
    db.refresh(user)
    return _to_out(user)


@router.post("/me/avatar", response_model=ProfileOut)
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProfileOut:
    ext = ALLOWED_MIME.get(file.content_type or "")
    if ext is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Avatar must be png, jpeg, or webp",
        )
    data = await file.read()
    if len(data) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )
    if len(data) > MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Avatar exceeds 2 MB limit",
        )

    _delete_prior_avatar(user)
    filename = f"{user.id}_{uuid4().hex}.{ext}"
    (UPLOAD_DIR / filename).write_bytes(data)

    user.avatar_url = f"/uploads/avatars/{filename}"
    db.commit()
    db.refresh(user)
    return _to_out(user)


@router.delete("/me/avatar", response_model=ProfileOut)
def delete_avatar(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProfileOut:
    _delete_prior_avatar(user)
    user.avatar_url = None
    db.commit()
    db.refresh(user)
    return _to_out(user)
