"""
Integration API Routes

Endpoints for managing OAuth connections to external systems.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.middleware.rbac import (
    CurrentUser,
    Permission,
    require_permission,
)
from backend.models.integration import (
    Integration,
    IntegrationProvider,
    IntegrationStatus,
    PROVIDER_CATEGORIES,
)
from backend.models.organization import Organization

router = APIRouter()


async def get_organization_or_404(org_id: UUID, db: AsyncSession) -> Organization:
    """Helper to get organization or raise 404."""
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {org_id} not found",
        )
    return org


@router.get(
    "/",
    summary="List integrations",
    description="List all connected integrations for an organization.",
)
async def list_integrations(
    org_id: UUID,
    category: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.INTEGRATION_READ)),
) -> list[dict]:
    """List integrations for organization."""
    await get_organization_or_404(org_id, db)

    query = select(Integration).where(Integration.organization_id == org_id)

    if category:
        query = query.where(Integration.provider_category == category)
    if status_filter:
        query = query.where(Integration.status == status_filter)

    result = await db.execute(query)
    integrations = result.scalars().all()

    return [
        {
            "id": str(i.id),
            "provider": i.provider,
            "provider_category": i.provider_category,
            "display_name": i.display_name or i.provider.upper(),
            "status": i.status,
            "last_sync_at": i.last_sync_at.isoformat() if i.last_sync_at else None,
            "last_sync_status": i.last_sync_status,
            "last_sync_records": i.last_sync_records,
            "last_error": i.last_error,
            "created_at": i.created_at.isoformat(),
        }
        for i in integrations
    ]


@router.get(
    "/providers",
    summary="List available providers",
    description="List all available integration providers.",
)
async def list_providers(
    user: CurrentUser = Depends(require_permission(Permission.INTEGRATION_READ)),
) -> list[dict]:
    """List available integration providers."""
    providers = []
    for provider in IntegrationProvider:
        category = PROVIDER_CATEGORIES.get(provider, "unknown")
        providers.append(
            {
                "provider": provider.value,
                "category": category.value if hasattr(category, "value") else category,
                "display_name": provider.value.replace("_", " ").title(),
            }
        )
    return providers


@router.post(
    "/connect/{provider}",
    summary="Initiate OAuth connection",
    description="Start OAuth flow to connect an integration.",
)
async def connect_integration(
    org_id: UUID,
    provider: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.INTEGRATION_WRITE)),
) -> dict:
    """Initiate OAuth connection."""
    await get_organization_or_404(org_id, db)

    # Validate provider
    try:
        provider_enum = IntegrationProvider(provider.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown provider: {provider}",
        )

    # Check for existing integration
    existing = await db.execute(
        select(Integration).where(
            Integration.organization_id == org_id,
            Integration.provider == provider_enum.value,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Integration with {provider} already exists",
        )

    # Get category
    category = PROVIDER_CATEGORIES.get(provider_enum, "unknown")

    # Create pending integration
    integration = Integration(
        organization_id=org_id,
        provider=provider_enum.value,
        provider_category=category.value if hasattr(category, "value") else category,
        status=IntegrationStatus.PENDING.value,
    )
    db.add(integration)
    await db.flush()
    await db.refresh(integration)

    # Store state for CSRF validation
    import secrets as _secrets

    oauth_state = _secrets.token_urlsafe(32)
    integration.oauth_state = oauth_state
    await db.flush()

    # Build real OAuth authorization URL
    from urllib.parse import urlencode

    from backend.config import get_settings
    from integrations.oauth_manager import get_oauth_config

    settings = get_settings()
    oauth_config = get_oauth_config(provider_enum.value)

    if not oauth_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth not configured for provider: {provider}",
        )

    # Build callback URL
    callback_url = (
        f"{settings.api_v1_prefix}/organizations/{org_id}"
        f"/integrations/callback/{provider_enum.value}"
    )

    params = {
        "response_type": "code",
        "client_id": getattr(settings, f"{provider_enum.value}_client_id", ""),
        "redirect_uri": callback_url,
        "scope": " ".join(oauth_config["scopes"]),
        "state": oauth_state,
    }

    oauth_url = f"{oauth_config['authorize_url']}?{urlencode(params)}"

    return {
        "integration_id": str(integration.id),
        "provider": provider,
        "oauth_url": oauth_url,
        "message": "Redirect user to oauth_url to complete connection",
    }


@router.get(
    "/callback/{provider}",
    summary="OAuth callback",
    description="Handle OAuth callback from provider.",
)
async def oauth_callback(
    org_id: UUID,
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.INTEGRATION_WRITE)),
) -> dict:
    """Handle OAuth callback."""
    # State should be the integration ID
    try:
        integration_id = UUID(state)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter",
        )

    result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.organization_id == org_id,
        )
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )

    # Exchange authorization code for tokens
    from datetime import datetime, timedelta, timezone

    import httpx

    from backend.config import get_settings
    from integrations.oauth_manager import OAuthTokenManager, get_oauth_config

    settings = get_settings()
    oauth_config = get_oauth_config(integration.provider)

    if not oauth_config:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth config missing for {integration.provider}",
        )

    callback_url = (
        f"{settings.api_v1_prefix}/organizations/{org_id}"
        f"/integrations/callback/{provider}"
    )

    token_payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": callback_url,
        "client_id": getattr(settings, f"{integration.provider}_client_id", ""),
        "client_secret": getattr(settings, f"{integration.provider}_client_secret", ""),
    }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(oauth_config["token_url"], data=token_payload)
            resp.raise_for_status()
            token_data = resp.json()
        except httpx.HTTPError as e:
            integration.status = IntegrationStatus.ERROR.value
            integration.last_error = f"Token exchange failed: {e}"
            await db.flush()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to exchange code for tokens: {e}",
            )

    # Encrypt and store tokens
    token_manager = OAuthTokenManager(settings.encryption_key)
    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token")

    enc_access, enc_refresh = token_manager.encrypt_tokens(access_token, refresh_token)
    integration.access_token_encrypted = enc_access
    integration.refresh_token_encrypted = enc_refresh

    expires_in = token_data.get("expires_in")
    if expires_in:
        integration.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))

    integration.status = IntegrationStatus.CONNECTED.value
    integration.scopes = oauth_config["scopes"]
    integration.oauth_state = None  # Clear state after use

    await db.flush()

    return {
        "integration_id": str(integration.id),
        "provider": provider,
        "status": "connected",
        "message": "Integration connected successfully",
    }


@router.delete(
    "/{integration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect integration",
    description="Disconnect and remove an integration.",
)
async def disconnect_integration(
    org_id: UUID,
    integration_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.INTEGRATION_WRITE)),
) -> None:
    """Disconnect integration."""
    result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.organization_id == org_id,
        )
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration {integration_id} not found",
        )

    # TODO: Revoke tokens at provider if supported
    await db.delete(integration)
    await db.flush()


@router.post(
    "/{integration_id}/sync",
    summary="Trigger sync",
    description="Manually trigger a data sync from the integration.",
)
async def trigger_sync(
    org_id: UUID,
    integration_id: UUID,
    full_sync: bool = False,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.INTEGRATION_SYNC)),
) -> dict:
    """Trigger manual sync."""
    result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.organization_id == org_id,
        )
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration {integration_id} not found",
        )

    if integration.status != IntegrationStatus.CONNECTED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot sync integration in status '{integration.status}'",
        )

    # Trigger async sync task via Celery
    from workers.tasks.sync_tasks import sync_integration as sync_task

    sync_task.delay(str(integration_id))

    return {
        "integration_id": str(integration_id),
        "provider": integration.provider,
        "sync_type": "full" if full_sync else "incremental",
        "status": "queued",
        "message": "Sync has been queued",
    }


@router.get(
    "/{integration_id}/status",
    summary="Get integration status",
    description="Get detailed status and sync history for an integration.",
)
async def get_integration_status(
    org_id: UUID,
    integration_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(Permission.INTEGRATION_READ)),
) -> dict:
    """Get detailed integration status."""
    result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.organization_id == org_id,
        )
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration {integration_id} not found",
        )

    return {
        "id": str(integration.id),
        "provider": integration.provider,
        "provider_category": integration.provider_category,
        "display_name": integration.display_name or integration.provider.upper(),
        "status": integration.status,
        "last_error": integration.last_error,
        "error_count": integration.error_count,
        "last_sync_at": integration.last_sync_at.isoformat() if integration.last_sync_at else None,
        "last_sync_status": integration.last_sync_status,
        "last_sync_records": integration.last_sync_records,
        "next_sync_at": integration.next_sync_at.isoformat() if integration.next_sync_at else None,
        "scopes": integration.scopes,
        "provider_metadata": integration.provider_metadata,
        "created_at": integration.created_at.isoformat(),
        "updated_at": integration.updated_at.isoformat(),
    }
