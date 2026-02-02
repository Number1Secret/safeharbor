"""
SSO Service

SAML and OIDC Single Sign-On integration for enterprise customers.
"""

import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SSOProvider(BaseModel):
    """SSO provider configuration."""
    id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    protocol: str  # "saml" or "oidc"
    name: str
    is_active: bool = True

    # SAML config
    idp_entity_id: str | None = None
    idp_sso_url: str | None = None
    idp_certificate: str | None = None

    # OIDC config
    client_id: str | None = None
    client_secret: str | None = None
    issuer_url: str | None = None
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    userinfo_endpoint: str | None = None

    # Mapping
    email_attribute: str = "email"
    name_attribute: str = "name"
    role_attribute: str | None = None
    role_mapping: dict[str, str] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=datetime.utcnow)


class SSOService:
    """Manages SSO configuration and authentication."""

    def __init__(self, db_session):
        self.db = db_session

    async def configure_saml(
        self,
        organization_id: UUID,
        name: str,
        idp_entity_id: str,
        idp_sso_url: str,
        idp_certificate: str,
        email_attribute: str = "email",
        role_mapping: dict | None = None,
    ) -> SSOProvider:
        """Configure SAML SSO for an organization."""
        provider = SSOProvider(
            organization_id=organization_id,
            protocol="saml",
            name=name,
            idp_entity_id=idp_entity_id,
            idp_sso_url=idp_sso_url,
            idp_certificate=idp_certificate,
            email_attribute=email_attribute,
            role_mapping=role_mapping or {},
        )

        logger.info(f"SAML SSO configured for org {organization_id}: {name}")
        return provider

    async def configure_oidc(
        self,
        organization_id: UUID,
        name: str,
        client_id: str,
        client_secret: str,
        issuer_url: str,
        role_mapping: dict | None = None,
    ) -> SSOProvider:
        """Configure OIDC SSO for an organization."""
        # Discover OIDC endpoints from issuer
        endpoints = await self._discover_oidc_endpoints(issuer_url)

        provider = SSOProvider(
            organization_id=organization_id,
            protocol="oidc",
            name=name,
            client_id=client_id,
            client_secret=client_secret,
            issuer_url=issuer_url,
            authorization_endpoint=endpoints.get("authorization_endpoint"),
            token_endpoint=endpoints.get("token_endpoint"),
            userinfo_endpoint=endpoints.get("userinfo_endpoint"),
            role_mapping=role_mapping or {},
        )

        logger.info(f"OIDC SSO configured for org {organization_id}: {name}")
        return provider

    async def initiate_login(
        self,
        provider: SSOProvider,
        redirect_uri: str,
    ) -> dict[str, str]:
        """
        Initiate SSO login flow.

        Returns URL to redirect the user to for authentication.
        """
        if provider.protocol == "saml":
            return await self._initiate_saml_login(provider, redirect_uri)
        elif provider.protocol == "oidc":
            return await self._initiate_oidc_login(provider, redirect_uri)
        else:
            raise ValueError(f"Unsupported SSO protocol: {provider.protocol}")

    async def handle_callback(
        self,
        provider: SSOProvider,
        callback_data: dict,
    ) -> dict[str, Any]:
        """
        Handle SSO callback after user authenticates.

        Returns user info extracted from the SSO response.
        """
        if provider.protocol == "saml":
            return await self._handle_saml_callback(provider, callback_data)
        elif provider.protocol == "oidc":
            return await self._handle_oidc_callback(provider, callback_data)
        else:
            raise ValueError(f"Unsupported SSO protocol: {provider.protocol}")

    async def _discover_oidc_endpoints(self, issuer_url: str) -> dict:
        """Discover OIDC provider endpoints from .well-known configuration."""
        import httpx

        discovery_url = f"{issuer_url.rstrip('/')}/.well-known/openid-configuration"
        async with httpx.AsyncClient() as client:
            response = await client.get(discovery_url)
            response.raise_for_status()
            return response.json()

    async def _initiate_saml_login(
        self,
        provider: SSOProvider,
        redirect_uri: str,
    ) -> dict[str, str]:
        """Generate SAML AuthnRequest and return redirect info."""
        import base64
        import zlib
        from datetime import datetime, timezone
        from uuid import uuid4

        request_id = f"_safeharbor_{uuid4().hex}"
        issue_instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        sp_entity_id = "https://app.safeharbor.ai/saml/metadata"
        acs_url = redirect_uri

        # Build SAML AuthnRequest XML
        authn_request = f"""<samlp:AuthnRequest
    xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
    ID="{request_id}"
    Version="2.0"
    IssueInstant="{issue_instant}"
    Destination="{provider.idp_sso_url}"
    AssertionConsumerServiceURL="{acs_url}"
    ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">
    <saml:Issuer>{sp_entity_id}</saml:Issuer>
    <samlp:NameIDPolicy
        Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
        AllowCreate="true"/>
</samlp:AuthnRequest>"""

        # Deflate and base64 encode for HTTP-Redirect binding
        compressed = zlib.compress(authn_request.encode("utf-8"))[2:-4]
        encoded = base64.b64encode(compressed).decode("utf-8")

        from urllib.parse import urlencode

        redirect_params = urlencode({
            "SAMLRequest": encoded,
            "RelayState": redirect_uri,
        })

        return {
            "redirect_url": f"{provider.idp_sso_url}?{redirect_params}",
            "request_id": request_id,
            "method": "GET",
        }

    async def _initiate_oidc_login(
        self,
        provider: SSOProvider,
        redirect_uri: str,
    ) -> dict[str, str]:
        """Generate OIDC authorization URL."""
        import secrets
        from urllib.parse import urlencode

        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)

        params = {
            "client_id": provider.client_id or "",
            "response_type": "code",
            "scope": "openid email profile",
            "redirect_uri": redirect_uri,
            "state": state,
            "nonce": nonce,
        }

        auth_url = f"{provider.authorization_endpoint}?{urlencode(params)}"

        return {
            "redirect_url": auth_url,
            "state": state,
            "nonce": nonce,
        }

    async def _handle_saml_callback(
        self,
        provider: SSOProvider,
        callback_data: dict,
    ) -> dict[str, Any]:
        """
        Process SAML response and extract user attributes.

        Validates the assertion's signature and conditions,
        then extracts email, name, and optional role from the response.
        """
        import base64
        import xml.etree.ElementTree as ET

        saml_response_b64 = callback_data.get("SAMLResponse", "")
        if not saml_response_b64:
            raise ValueError("Missing SAMLResponse in callback data")

        # Decode the SAML response
        try:
            saml_xml = base64.b64decode(saml_response_b64).decode("utf-8")
        except Exception as e:
            raise ValueError(f"Failed to decode SAML response: {e}")

        # Parse XML
        ns = {
            "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
            "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
            "ds": "http://www.w3.org/2000/09/xmldsig#",
        }

        try:
            root = ET.fromstring(saml_xml)
        except ET.ParseError as e:
            raise ValueError(f"Invalid SAML XML: {e}")

        # Check status
        status_code = root.find(".//samlp:StatusCode", ns)
        if status_code is not None:
            status_value = status_code.get("Value", "")
            if "Success" not in status_value:
                raise ValueError(f"SAML authentication failed: {status_value}")

        # Extract assertion
        assertion = root.find(".//saml:Assertion", ns)
        if assertion is None:
            raise ValueError("No assertion found in SAML response")

        # Verify issuer matches configured IdP
        issuer = assertion.find("saml:Issuer", ns)
        if issuer is not None and provider.idp_entity_id:
            if issuer.text != provider.idp_entity_id:
                raise ValueError(
                    f"SAML issuer mismatch: expected {provider.idp_entity_id}, "
                    f"got {issuer.text}"
                )

        # Check conditions (audience and time validity)
        conditions = assertion.find("saml:Conditions", ns)
        if conditions is not None:
            from datetime import datetime, timezone

            not_before = conditions.get("NotBefore")
            not_on_or_after = conditions.get("NotOnOrAfter")
            now = datetime.now(timezone.utc)

            if not_before:
                nb = datetime.fromisoformat(not_before.replace("Z", "+00:00"))
                if now < nb:
                    raise ValueError("SAML assertion not yet valid")

            if not_on_or_after:
                noa = datetime.fromisoformat(not_on_or_after.replace("Z", "+00:00"))
                if now >= noa:
                    raise ValueError("SAML assertion has expired")

        # Extract NameID (email)
        name_id = assertion.find(".//saml:Subject/saml:NameID", ns)
        email = name_id.text if name_id is not None else ""

        # Extract attributes
        attributes: dict[str, str] = {}
        attr_statement = assertion.find("saml:AttributeStatement", ns)
        if attr_statement is not None:
            for attr in attr_statement.findall("saml:Attribute", ns):
                attr_name = attr.get("Name", "")
                attr_value_el = attr.find("saml:AttributeValue", ns)
                if attr_name and attr_value_el is not None and attr_value_el.text:
                    attributes[attr_name] = attr_value_el.text

        # Map attributes to user info
        user_email = attributes.get(provider.email_attribute, email)
        user_name = attributes.get(provider.name_attribute, "")

        # Map role if configured
        role = "viewer"
        if provider.role_attribute and provider.role_mapping:
            idp_role = attributes.get(provider.role_attribute)
            if idp_role:
                role = provider.role_mapping.get(idp_role, "viewer")

        if not user_email:
            raise ValueError("No email found in SAML assertion")

        logger.info(f"SAML login successful for {user_email} via {provider.name}")

        return {
            "email": user_email,
            "name": user_name,
            "role": role,
            "provider": provider.name,
            "external_id": name_id.text if name_id is not None else "",
            "attributes": attributes,
        }

    async def _handle_oidc_callback(
        self,
        provider: SSOProvider,
        callback_data: dict,
    ) -> dict[str, Any]:
        """Exchange OIDC code for tokens and get user info."""
        import httpx

        code = callback_data.get("code", "")
        redirect_uri = callback_data.get("redirect_uri", "")

        async with httpx.AsyncClient() as client:
            # Exchange code for tokens
            token_response = await client.post(
                provider.token_endpoint or "",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": provider.client_id or "",
                    "client_secret": provider.client_secret or "",
                },
            )
            token_response.raise_for_status()
            tokens = token_response.json()

            # Get user info
            userinfo_response = await client.get(
                provider.userinfo_endpoint or "",
                headers={
                    "Authorization": f"Bearer {tokens['access_token']}",
                },
            )
            userinfo_response.raise_for_status()
            userinfo = userinfo_response.json()

        # Map role if configured
        role = "viewer"
        if provider.role_attribute and provider.role_mapping:
            idp_role = userinfo.get(provider.role_attribute)
            if idp_role:
                role = provider.role_mapping.get(idp_role, "viewer")

        return {
            "email": userinfo.get(provider.email_attribute, ""),
            "name": userinfo.get(provider.name_attribute, ""),
            "role": role,
            "provider": provider.name,
            "external_id": userinfo.get("sub", ""),
        }
