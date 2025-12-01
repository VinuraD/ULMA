import os
import logging
from typing import Dict, Any

import requests
from requests.exceptions import RequestException
from dotenv import load_dotenv

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Route, Mount

from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData, INTERNAL_ERROR, INVALID_PARAMS

# Load environment variables from .env if present
load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Azure configuration from environment
TENANT_ID = os.getenv("AZURE_TENANT_ID")
CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
GRAPH_SCOPE = os.getenv("AZURE_GRAPH_SCOPE", "https://graph.microsoft.com/.default")
# Default M365 Business Standard SKU; override with env var if your tenant differs.
BUSINESS_STANDARD_SKU = os.getenv(
    "M365_BUSINESS_STANDARD_SKU_ID", "c42b9cae-ea4f-4ab7-9717-81576235ccac"
)

if not (TENANT_ID and CLIENT_ID and CLIENT_SECRET):
    logger.warning(
        "AZURE_TENANT_ID, AZURE_CLIENT_ID, and/or AZURE_CLIENT_SECRET are not set. "
        "Azure AD tools will fail until these are configured."
    )

AUTH_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# ---------------------------------------------------------------------------
# Helper functions for Microsoft Graph
# ---------------------------------------------------------------------------

def _get_graph_token() -> str:
    """Get an app-only access token for Microsoft Graph using client credentials."""
    if not (TENANT_ID and CLIENT_ID and CLIENT_SECRET):
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message=(
                    "Azure AD credentials are not configured. "
                    "Set AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET."
                ),
            )
        )

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials",
        "scope": GRAPH_SCOPE,
    }

    try:
        resp = requests.post(AUTH_URL, data=data, timeout=10)
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if not token:
            raise McpError(
                ErrorData(
                    code=INTERNAL_ERROR,
                    message="No access_token in token response from Azure AD.",
                )
            )
        return token
    except RequestException as e:
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message=f"Failed to acquire token from Azure AD: {e}",
            )
        ) from e


def _graph_headers() -> Dict[str, str]:
    token = _get_graph_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _graph_get(url: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    try:
        resp = requests.get(url, headers=_graph_headers(), params=params, timeout=10)
        if resp.status_code == 404:
            raise McpError(
                ErrorData(
                    code=INVALID_PARAMS,
                    message=f"Resource not found for URL: {url}",
                )
            )
        resp.raise_for_status()
        return resp.json()
    except McpError:
        raise
    except RequestException as e:
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message=f"Graph GET request failed: {e}",
            )
        ) from e


def _graph_post(url: str, body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        resp = requests.post(url, headers=_graph_headers(), json=body, timeout=10)
        resp.raise_for_status()
        # Some operations (like adding a member to a group) return 204 with no JSON
        if resp.text.strip():
            return resp.json()
        return {"status": "success", "http_status": resp.status_code}
    except RequestException as e:
        resp = getattr(e, "response", None)
        detail = ""
        if resp is not None:
            try:
                detail = resp.text
            except Exception:
                detail = ""
        msg = (
            f"Graph POST request failed: HTTP {getattr(resp, 'status_code', 'n/a')} - {e}"
        )
        if detail:
            msg += f" | response: {detail}"
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message=msg,
            )
        ) from e


def _graph_patch(url: str, body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        resp = requests.patch(url, headers=_graph_headers(), json=body, timeout=10)
        resp.raise_for_status()
        if resp.text.strip():
            return resp.json()
        return {"status": "success", "http_status": resp.status_code}
    except RequestException as e:
        msg = f"Graph PATCH request failed: HTTP {getattr(e.response, 'status_code', 'n/a')} - {e}"
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message=msg,
            )
        ) from e


def _graph_delete(url: str) -> Dict[str, Any]:
    try:
        resp = requests.delete(url, headers=_graph_headers(), timeout=10)
        if resp.status_code == 404:
            raise McpError(
                ErrorData(
                    code=INVALID_PARAMS,
                    message=f"Resource not found for URL: {url}",
                )
            )
        resp.raise_for_status()
        # DELETE /users returns 204 No Content on success
        return {"status": "success", "http_status": resp.status_code}
    except McpError:
        raise
    except RequestException as e:
        msg = f"Graph DELETE request failed: HTTP {getattr(e.response, 'status_code', 'n/a')} - {e}"
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message=msg,
            )
        ) from e


# ---------------------------------------------------------------------------
# MCP server definition
# ---------------------------------------------------------------------------

mcp = FastMCP("azure-ad-mcp")


@mcp.tool()
def azure_get_user(upn: str) -> Dict[str, Any]:
    """
    Get an Azure AD user by userPrincipalName (UPN).

    Args:
        upn: User principal name, e.g. "john.doe@contoso.onmicrosoft.com"

    Returns:
        A subset of the user object from Microsoft Graph.
    """
    if not upn:
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message="Parameter 'upn' is required.",
            )
        )

    url = f"{GRAPH_BASE}/users/{upn}"
    user = _graph_get(url)

    # Return only a safe subset of fields to the LLM
    fields_to_keep = [
        "id",
        "displayName",
        "userPrincipalName",
        "mail",
        "accountEnabled",
        "jobTitle",
        "department",
    ]
    filtered = {k: v for k, v in user.items() if k in fields_to_keep}
    return filtered


@mcp.tool()
def azure_create_user(upn: str, display_name: str, password: str) -> Dict[str, Any]:
    """
    Create a new Azure AD user.

    Args:
        upn: New user's userPrincipalName, e.g. "new.user@contoso.onmicrosoft.com"
        display_name: User's display name.
        password: Initial password. (Typically you'd generate this server-side.)

    Returns:
        Basic info for the created user.
    """
    if not upn or not display_name or not password:
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message="Parameters 'upn', 'display_name', and 'password' are required.",
            )
        )

    body = {
        "accountEnabled": True,
        "displayName": display_name,
        "mailNickname": upn.split("@")[0],
        "userPrincipalName": upn,
        "passwordProfile": {
            "forceChangePasswordNextSignIn": True,
            "password": password,
        },
    }

    url = f"{GRAPH_BASE}/users"
    created = _graph_post(url, body)

    # Immediately assign Microsoft 365 Business Standard by default
    user_id = created.get("id")
    license_result: Dict[str, Any] | None = None
    if user_id:
        try:
            _assign_business_standard_license(user_id=user_id)
            license_result = {"status": "success", "skuId": BUSINESS_STANDARD_SKU}
        except Exception as exc:
            # Surface the error but do not swallow the created user
            license_result = {
                "status": "failed",
                "skuId": BUSINESS_STANDARD_SKU,
                "error": str(exc),
            }

    fields_to_keep = [
        "id",
        "displayName",
        "userPrincipalName",
        "mailNickname",
        "accountEnabled",
    ]
    response = {k: v for k, v in created.items() if k in fields_to_keep}
    if license_result:
        response["license_assignment"] = license_result
    return response


@mcp.tool()
def azure_add_user_to_group(user_upn: str, group_id: str) -> Dict[str, Any]:
    """
    Add a user to an Azure AD group.

    Args:
        user_upn: User principal name, e.g. "john.doe@contoso.onmicrosoft.com"
        group_id: Object ID of the group (not the displayName).

    Returns:
        A small status object.
    """
    if not user_upn or not group_id:
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message="Parameters 'user_upn' and 'group_id' are required.",
            )
        )

    # First resolve the user to an object ID
    user_url = f"{GRAPH_BASE}/users/{user_upn}"
    user = _graph_get(user_url)
    user_id = user.get("id")
    if not user_id:
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message=f"Could not resolve user ID for '{user_upn}'.",
            )
        )

    # POST /groups/{id}/members/$ref with directoryObjects reference
    group_url = f"{GRAPH_BASE}/groups/{group_id}/members/$ref"
    body = {
        "@odata.id": f"{GRAPH_BASE}/directoryObjects/{user_id}"
    }

    _graph_post(group_url, body)

    return {
        "status": "success",
        "message": f"User {user_upn} added to group {group_id}.",
    }


@mcp.tool()
def azure_delete_user(upn_or_id: str) -> Dict[str, Any]:
    """
    Delete an Azure AD user.

    Args:
        upn_or_id: The user's userPrincipalName or object ID.

    Returns:
        A small status object.
    """
    if not upn_or_id:
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message="Parameter 'upn_or_id' is required.",
            )
        )

    url = f"{GRAPH_BASE}/users/{upn_or_id}"
    result = _graph_delete(url)

    return {
        "status": result.get("status", "success"),
        "message": f"User '{upn_or_id}' deleted (moved to deleted items).",
        "http_status": result.get("http_status"),
    }


@mcp.tool()
def azure_reset_user_password(
    upn: str,
    new_password: str,
    force_change_next_sign_in: bool = True,
) -> Dict[str, Any]:
    """
    Reset a user's password by updating passwordProfile.

    Args:
        upn: User principal name, e.g. "john.doe@contoso.onmicrosoft.com".
        new_password: New password to set.
        force_change_next_sign_in: Whether the user must change the password at next sign-in.

    Returns:
        A small status object.
    """
    if not upn or not new_password:
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message="Parameters 'upn' and 'new_password' are required.",
            )
        )

    url = f"{GRAPH_BASE}/users/{upn}"
    body = {
        "passwordProfile": {
            "password": new_password,
            "forceChangePasswordNextSignIn": force_change_next_sign_in,
        }
    }

    _graph_patch(url, body)

    return {
        "status": "success",
        "message": (
            f"Password reset for user '{upn}'. "
            f"forceChangePasswordNextSignIn={force_change_next_sign_in}"
        ),
    }


@mcp.tool()
def azure_grant_app_access(
    user_upn: str,
    app_object_id: str,
    app_role_id: str | None = None,
) -> Dict[str, Any]:
    """
    Grant a user access to an application by creating an app role assignment.

    Args:
        user_upn: User principal name, e.g. "john@contoso.com".
        app_object_id: The application's object ID (resourceId).
        app_role_id: The app role GUID. Default is the "default" app role (all zeroes).
    """
    if not user_upn or not app_object_id:
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message="Parameters 'user_upn' and 'app_object_id' are required.",
            )
        )

    # Resolve user to object ID
    user = _graph_get(f"{GRAPH_BASE}/users/{user_upn}")
    user_id = user.get("id")
    if not user_id:
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message=f"Could not resolve user ID for '{user_upn}'.",
            )
        )

    # Determine a valid app role id; if none provided, pick the first enabled role for users
    role_id = app_role_id
    if not role_id:
        sp = _graph_get(f"{GRAPH_BASE}/servicePrincipals/{app_object_id}")
        roles = sp.get("appRoles", []) if isinstance(sp, dict) else []
        candidate = next(
            (
                r
                for r in roles
                if r.get("isEnabled") and "User" in (r.get("allowedMemberTypes") or [])
            ),
            None,
        )
        if not candidate:
            raise McpError(
                ErrorData(
                    code=INVALID_PARAMS,
                    message=(
                        f"No enabled user appRole found for app {app_object_id}. "
                        "Specify a valid app_role_id."
                    ),
                )
            )
        role_id = candidate.get("id")

    assignment_body = {
        "principalId": user_id,
        "resourceId": app_object_id,
        "appRoleId": role_id,
    }

    created = _graph_post(
        f"{GRAPH_BASE}/users/{user_id}/appRoleAssignments", assignment_body
    )

    return {
        "status": "success",
        "message": f"Granted app access for user {user_upn} to app {app_object_id}.",
        "assignment": created,
    }


@mcp.tool()
def azure_grant_app_access_by_name(
    user_upn: str,
    app_name: str,
    app_role_id: str | None = None,
) -> Dict[str, Any]:
    """
    Convenience helper to grant app access by application display name.

    Resolves the service principal by displayName prefix match and delegates to
    azure_grant_app_access. If multiple apps match, returns an error with the
    candidate list so the caller can disambiguate.

    Args:
        user_upn: User principal name.
        app_name: Application display name (prefix match).
        app_role_id: Optional app role id; if omitted, first enabled user role is used.
    """
    if not user_upn or not app_name:
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message="Parameters 'user_upn' and 'app_name' are required.",
            )
        )

    params = {
        "$filter": f"startswith(displayName,'{app_name}')",
        "$select": "id,displayName",
    }
    resp = _graph_get(f"{GRAPH_BASE}/servicePrincipals", params=params)
    items = resp.get("value", []) if isinstance(resp, dict) else []

    if not items:
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message=f"No application found matching '{app_name}'.",
            )
        )
    if len(items) > 1 and not any(sp["displayName"] == app_name for sp in items):
        names = [f"{sp.get('displayName')} ({sp.get('id')})" for sp in items]
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message=(
                    "Multiple applications matched; please specify one of: "
                    + "; ".join(names)
                ),
            )
        )

    # choose exact match if present, else first
    chosen = next((sp for sp in items if sp.get("displayName") == app_name), items[0])
    app_object_id = chosen.get("id")
    return azure_grant_app_access(user_upn=user_upn, app_object_id=app_object_id, app_role_id=app_role_id)


@mcp.tool()
def azure_revoke_app_access(
    user_upn: str,
    app_object_id: str | None = None,
    assignment_id: str | None = None,
) -> Dict[str, Any]:
    """
    Revoke a user's access to an application by deleting the app role assignment.

    Args:
        user_upn: User principal name.
        app_object_id: The application's object ID; used to locate the assignment if assignment_id not given.
        assignment_id: Specific appRoleAssignment ID to delete (preferred).
    """
    if not user_upn:
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message="Parameter 'user_upn' is required.",
            )
        )

    # Resolve user to object ID
    user = _graph_get(f"{GRAPH_BASE}/users/{user_upn}")
    user_id = user.get("id")
    if not user_id:
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message=f"Could not resolve user ID for '{user_upn}'.",
            )
        )

    target_assignment_id = assignment_id

    # If we weren't given a specific assignment ID, try to find one by app_object_id
    if not target_assignment_id:
        if not app_object_id:
            raise McpError(
                ErrorData(
                    code=INVALID_PARAMS,
                    message="Provide either 'assignment_id' or 'app_object_id'.",
                )
            )
        assignments = _graph_get(f"{GRAPH_BASE}/users/{user_id}/appRoleAssignments")
        items = assignments.get("value", []) if isinstance(assignments, dict) else []
        match = next(
            (item for item in items if item.get("resourceId") == app_object_id), None
        )
        if not match:
            raise McpError(
                ErrorData(
                    code=INVALID_PARAMS,
                    message=(
                        f"No app role assignment found for user '{user_upn}' "
                        f"and app '{app_object_id}'."
                    ),
                )
            )
        target_assignment_id = match.get("id")

    _graph_delete(
        f"{GRAPH_BASE}/users/{user_id}/appRoleAssignments/{target_assignment_id}"
    )

    return {
        "status": "success",
        "message": (
            f"Revoked app access for user {user_upn}; "
            f"assignment_id={target_assignment_id}."
        ),
    }


@mcp.tool()
def azure_find_groups(group_name: str) -> Dict[str, Any]:
    """
    Find Azure AD groups by display name (prefix match).

    Args:
        group_name: Partial or full display name to search (prefix).
    """
    if not group_name:
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message="Parameter 'group_name' is required.",
            )
        )

    params = {"$filter": f"startswith(displayName,'{group_name}')", "$select": "id,displayName,mailNickname"}
    resp = _graph_get(f"{GRAPH_BASE}/groups", params=params)
    items = resp.get("value", []) if isinstance(resp, dict) else []

    return {"count": len(items), "groups": items}


@mcp.tool()
def azure_find_apps(app_name: str) -> Dict[str, Any]:
    """
    Find enterprise applications (service principals) by display name (prefix match).

    Args:
        app_name: Partial or full display name to search (prefix).
    """
    if not app_name:
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message="Parameter 'app_name' is required.",
            )
        )

    params = {
        "$filter": f"startswith(displayName,'{app_name}')",
        "$select": "id,appId,displayName",
    }
    resp = _graph_get(f"{GRAPH_BASE}/servicePrincipals", params=params)
    items = resp.get("value", []) if isinstance(resp, dict) else []

    return {"count": len(items), "apps": items}


def _list_subscribed_skus() -> list[dict[str, Any]]:
    """Return the tenant's subscribed SKUs."""
    resp = _graph_get(f"{GRAPH_BASE}/subscribedSkus")
    return resp.get("value", []) if isinstance(resp, dict) else []


def _resolve_business_standard_sku(preferred_sku: str | None = None) -> dict[str, Any]:
    """
    Resolve the SKU object for Business Standard (or a preferred SKU GUID/part number).
    """
    skus = _list_subscribed_skus()
    if not skus:
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message="No subscribed SKUs returned by Graph; cannot assign license.",
            )
        )

    # If a specific skuId or skuPartNumber was provided, try to match it first.
    if preferred_sku:
        match = next(
            (
                s
                for s in skus
                if s.get("skuId") == preferred_sku
                or s.get("skuPartNumber") == preferred_sku
            ),
            None,
        )
        if not match:
            candidates = [f"{s.get('skuPartNumber')} ({s.get('skuId')})" for s in skus]
            raise McpError(
                ErrorData(
                    code=INVALID_PARAMS,
                    message=(
                        f"Requested SKU '{preferred_sku}' not found. "
                        f"Available: {', '.join(candidates)}"
                    ),
                )
            )
        return match

    # Known Business Standard identifiers: skuPartNumber O365_BUSINESS_PREMIUM or display name contains "Business Standard"
    match = next(
        (
            s
            for s in skus
            if s.get("skuPartNumber") == "O365_BUSINESS_PREMIUM"
            or "Business Standard" in (s.get("skuPartNumber") or "")
            or "Business Standard" in (s.get("prepaidUnits") and "")
            or "Business Standard" in (s.get("displayName") or "")
        ),
        None,
    )
    if not match:
        candidates = [f"{s.get('skuPartNumber')} ({s.get('skuId')})" for s in skus]
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message=(
                    "Could not locate a Business Standard SKU in tenant. "
                    f"Available SKUs: {', '.join(candidates)}"
                ),
            )
        )
    return match


def _ensure_sku_has_capacity(sku: dict[str, Any]) -> None:
    """Raise if the SKU has no available units."""
    consumed = sku.get("consumedUnits", 0) or 0
    prepaid = sku.get("prepaidUnits", {}) or {}
    enabled = prepaid.get("enabled") or 0
    warning = prepaid.get("warning") or 0
    available = enabled - consumed
    if available <= 0 and warning <= 0:
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message=(
                    f"SKU {sku.get('skuPartNumber')} has no available licenses "
                    f"(enabled={enabled}, consumed={consumed})."
                ),
            )
        )


def _assign_business_standard_license(
    user_id: str | None = None,
    user_upn: str | None = None,
    preferred_sku: str | None = None,
) -> Dict[str, Any]:
    """
    Internal helper to assign Microsoft 365 Business Standard (or override SKU) to a user.
    """
    if not user_id:
        if not user_upn:
            raise McpError(
                ErrorData(
                    code=INVALID_PARAMS,
                    message="Provide user_id or user_upn to assign a license.",
                )
            )
        user = _graph_get(f"{GRAPH_BASE}/users/{user_upn}")
        user_id = user.get("id")
    if not user_id:
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message="Could not resolve user for license assignment.",
            )
        )

    sku_obj = _resolve_business_standard_sku(preferred_sku or BUSINESS_STANDARD_SKU)
    _ensure_sku_has_capacity(sku_obj)

    body = {
        "addLicenses": [{"skuId": sku_obj.get("skuId")}],
        "removeLicenses": [],
    }
    return _graph_post(f"{GRAPH_BASE}/users/{user_id}/assignLicense", body)


@mcp.tool()
def azure_assign_business_standard_license(
    user_upn: str, sku_id: str | None = None
) -> Dict[str, Any]:
    """
    Assign Microsoft 365 Business Standard to a user (override SKU via sku_id if needed).

    Args:
        user_upn: User principal name.
        sku_id: Optional SKU GUID; defaults to BUSINESS_STANDARD_SKU env or compiled default.
    """
    sku_obj = _resolve_business_standard_sku(sku_id or BUSINESS_STANDARD_SKU)
    _ensure_sku_has_capacity(sku_obj)

    # Resolve user to object ID
    user = _graph_get(f"{GRAPH_BASE}/users/{user_upn}")
    user_id = user.get("id")
    if not user_id:
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message=f"Could not resolve user ID for '{user_upn}'.",
            )
        )

    body = {"addLicenses": [{"skuId": sku_obj.get("skuId")}], "removeLicenses": []}
    result = _graph_post(f"{GRAPH_BASE}/users/{user_id}/assignLicense", body)

    return {
        "status": "success",
        "message": f"Assigned Business Standard license to {user_upn}.",
        "skuId": sku_obj.get("skuId"),
        "skuPartNumber": sku_obj.get("skuPartNumber"),
        "graph_result": result,
    }


# ---------------------------------------------------------------------------
# SSE transport wiring (compatible with Google ADK MCPToolset)
# ---------------------------------------------------------------------------

sse = SseServerTransport("/messages/")


async def handle_sse(request: Request) -> None:
    """Handle SSE connections for MCP."""
    _server = mcp._mcp_server
    async with sse.connect_sse(
        request.scope,
        request.receive,
        request._send,
    ) as (reader, writer):
        await _server.run(
            reader,
            writer,
            _server.create_initialization_options(),
        )
    # Starlette expects a Response; return an empty one to avoid NoneType errors on disconnect
    from starlette.responses import Response
    return Response()


app = Starlette(
    debug=True,
    routes=[
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ],
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
