"""
SSO Router

SAML and OIDC Single Sign-On endpoints for enterprise customers.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.middleware.rbac import CurrentUser, Permission, require_permission
from backend.services.sso import SSOProvider, SSOService

router = APIRouter()


# ── Schemas ───────────────────────────────────────────


class SAMLConfigRequest(BaseModel):
    """Configure SAML SSO."""
    name: str
    idp_entity_id: str
    idp_sso_url: str
    idp_certificate: str
    email_attribute: str = "email"
    role_mapping: dict[str, str] | None = None


class OIDCConfigRequest(BaseModel):
    """Configure OIDC SSO."""
    name: str
    client_id: str
    client_secret: str
    issuer_url: str
    role_mapping: dict[str, str] | None = None


class SSOLoginResponse(BaseModel):
    """SSO login redirect info."""
    redirect_url: str
    request_id: str | None = None
    state: str | None = None


class SSOProviderResponse(BaseModel):
    """SSO provider info (no secrets)."""
    id: UUID
    protocol: str
    name: str
    is_active: bool
    idp_entity_id: str | None = None
    issuer_url: str | None = None


# ── Endpoints ─────────────────────────────────────────


@router.post("/sso/saml/configure", response_model=SSOProviderResponse)
async def configure_saml(
    org_id: UUID,
    body: SAMLConfigRequest,
    user: CurrentUser = Depends(require_permission(Permission.ADMIN_SSO)),
    db: AsyncSession = Depends(get_db),
):
    """Configure SAML SSO for the organization."""
    if str(user.organization_id) != str(org_id):
        raise HTTPException(status_code=403, detail="Access denied")

    svc = SSOService(db)
    provider = await svc.configure_saml(
        organization_id=org_id,
        name=body.name,
        idp_entity_id=body.idp_entity_id,
        idp_sso_url=body.idp_sso_url,
        idp_certificate=body.idp_certificate,
        email_attribute=body.email_attribute,
        role_mapping=body.role_mapping,
    )

    return SSOProviderResponse(
        id=provider.id,
        protocol=provider.protocol,
        name=provider.name,
        is_active=provider.is_active,
        idp_entity_id=provider.idp_entity_id,
    )


@router.post("/sso/oidc/configure", response_model=SSOProviderResponse)
async def configure_oidc(
    org_id: UUID,
    body: OIDCConfigRequest,
    user: CurrentUser = Depends(require_permission(Permission.ADMIN_SSO)),
    db: AsyncSession = Depends(get_db),
):
    """Configure OIDC SSO for the organization."""
    if str(user.organization_id) != str(org_id):
        raise HTTPException(status_code=403, detail="Access denied")

    svc = SSOService(db)
    provider = await svc.configure_oidc(
        organization_id=org_id,
        name=body.name,
        client_id=body.client_id,
        client_secret=body.client_secret,
        issuer_url=body.issuer_url,
        role_mapping=body.role_mapping,
    )

    return SSOProviderResponse(
        id=provider.id,
        protocol=provider.protocol,
        name=provider.name,
        is_active=provider.is_active,
        issuer_url=provider.issuer_url,
    )


@router.get("/sso/metadata")
async def get_sp_metadata():
    """Return SAML Service Provider metadata XML."""
    sp_entity_id = "https://app.safeharbor.ai/saml/metadata"
    acs_url = "https://app.safeharbor.ai/api/v1/auth/sso/saml/callback"

    metadata = f"""<?xml version="1.0" encoding="UTF-8"?>
<md:EntityDescriptor
    xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
    entityID="{sp_entity_id}">
    <md:SPSSODescriptor
        AuthnRequestsSigned="false"
        WantAssertionsSigned="true"
        protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
        <md:NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</md:NameIDFormat>
        <md:AssertionConsumerService
            Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
            Location="{acs_url}"
            index="0"
            isDefault="true"/>
    </md:SPSSODescriptor>
</md:EntityDescriptor>"""

    from starlette.responses import Response

    return Response(content=metadata, media_type="application/xml")
