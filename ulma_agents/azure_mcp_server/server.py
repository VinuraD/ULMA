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
        msg = f"Graph POST request failed: HTTP {getattr(e.response, 'status_code', 'n/a')} - {e}"
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

    fields_to_keep = [
        "id",
        "displayName",
        "userPrincipalName",
        "mailNickname",
        "accountEnabled",
    ]
    return {k: v for k, v in created.items() if k in fields_to_keep}


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
    app_role_id: str = "00000000-0000-0000-0000-000000000000",
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

    assignment_body = {
        "principalId": user_id,
        "resourceId": app_object_id,
        "appRoleId": app_role_id,
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
