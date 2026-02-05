"""
Auth Router

Registration, login, token refresh, password change, user profile,
and Google OAuth endpoints.
"""

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.middleware.rbac import CurrentUser, get_current_user
from backend.models.organization import Organization
from backend.models.user import User
from backend.schemas.auth import (
    ChangePasswordRequest,
    GoogleAuthRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from backend.services.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Register a new organization and owner user.

    Creates the organization, then creates the first user with the 'owner' role.
    Returns a JWT token pair so the user is immediately logged in.
    """
    # Check if email is already taken
    existing_user = await db.execute(select(User).where(User.email == body.email))
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Check if EIN is already taken
    existing_org = await db.execute(select(Organization).where(Organization.ein == body.ein))
    if existing_org.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organization with this EIN already exists",
        )

    # Create organization
    org = Organization(
        name=body.org_name,
        ein=body.ein,
    )
    db.add(org)
    await db.flush()  # Get org.id without committing

    # Create owner user
    user = User(
        organization_id=org.id,
        email=body.email,
        name=body.name,
        hashed_password=hash_password(body.password),
        role="owner",
        is_active=True,
        is_verified=True,  # Auto-verified on registration
    )
    db.add(user)
    await db.flush()

    # Generate tokens
    access_token = create_access_token(
        sub=str(user.id),
        email=user.email,
        org_id=str(org.id),
        role=user.role,
    )
    refresh_token = create_refresh_token(
        sub=str(user.id),
        org_id=str(org.id),
    )

    from backend.config import get_settings
    settings = get_settings()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with email and password, returns JWT token pair."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    access_token = create_access_token(
        sub=str(user.id),
        email=user.email,
        org_id=str(user.organization_id),
        role=user.role,
    )
    refresh_token = create_refresh_token(
        sub=str(user.id),
        org_id=str(user.organization_id),
    )

    from backend.config import get_settings
    settings = get_settings()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange a valid refresh token for a new token pair."""
    import jwt as pyjwt

    try:
        payload = decode_token(body.refresh_token)
    except pyjwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid refresh token: {e}",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is not a refresh token",
        )

    # Look up user to get current role/email (may have changed since last token)
    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    access_token = create_access_token(
        sub=str(user.id),
        email=user.email,
        org_id=str(user.organization_id),
        role=user.role,
    )
    new_refresh_token = create_refresh_token(
        sub=str(user.id),
        org_id=str(user.organization_id),
    )

    from backend.config import get_settings
    settings = get_settings()

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/google", response_model=TokenResponse)
async def google_auth(
    body: GoogleAuthRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with a Google ID token. Creates a new account if needed."""
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    from backend.config import get_settings
    settings = get_settings()

    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google sign-in is not configured",
        )

    # Verify the Google ID token
    try:
        idinfo = id_token.verify_oauth2_token(
            body.credential,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google ID token",
        )

    google_email = idinfo.get("email")
    google_name = idinfo.get("name", "")
    google_sub = idinfo.get("sub")  # Google's unique user ID

    if not google_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account has no email",
        )

    # Look up existing user by email
    result = await db.execute(select(User).where(User.email == google_email))
    user = result.scalar_one_or_none()

    if user:
        # Existing user — link Google SSO if not already linked
        if not user.sso_provider:
            user.sso_provider = "google"
            user.sso_external_id = google_sub

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated",
            )

        user.is_verified = True
        user.last_login_at = datetime.now(timezone.utc)
        await db.flush()
    else:
        # New user — create placeholder org and user
        # Generate a unique placeholder EIN (99-XXXXXXX range to avoid real EINs)
        placeholder_ein = f"99-{secrets.randbelow(9000000) + 1000000}"

        # Ensure EIN uniqueness
        existing_ein = await db.execute(
            select(Organization).where(Organization.ein == placeholder_ein)
        )
        while existing_ein.scalar_one_or_none():
            placeholder_ein = f"99-{secrets.randbelow(9000000) + 1000000}"
            existing_ein = await db.execute(
                select(Organization).where(Organization.ein == placeholder_ein)
            )

        org = Organization(
            name=f"{google_name}'s Organization" if google_name else "My Organization",
            ein=placeholder_ein,
        )
        db.add(org)
        await db.flush()

        user = User(
            organization_id=org.id,
            email=google_email,
            name=google_name,
            hashed_password=None,  # No password for Google-only users
            role="owner",
            is_active=True,
            is_verified=True,
            sso_provider="google",
            sso_external_id=google_sub,
            last_login_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.flush()

    # Generate tokens
    access_token = create_access_token(
        sub=str(user.id),
        email=user.email,
        org_id=str(user.organization_id),
        role=user.role,
    )
    refresh_token = create_refresh_token(
        sub=str(user.id),
        org_id=str(user.organization_id),
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Change the authenticated user's password."""
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password change not available for SSO users",
        )

    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    user.hashed_password = hash_password(body.new_password)
    await db.flush()


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Get the currently authenticated user's profile."""
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse.model_validate(user)
