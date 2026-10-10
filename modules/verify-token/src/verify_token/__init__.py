from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Final
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()

GRAPH_API_BASE: Final[str] = "https://graph.facebook.com"
DEFAULT_GRAPH_API_VERSION: Final[str] = "v26.0"
REQUEST_TIMEOUT_SECONDS: Final[float] = 15.0

REQUIRED_PERMISSIONS: Final[tuple[str, ...]] = (
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_posts",
)


class GraphAPIError(RuntimeError):
    """Represent a Graph API, HTTP, or network error without exposing tokens."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_type: str | None = None,
        error_code: int | None = None,
        error_subcode: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        self.error_code = error_code
        self.error_subcode = error_subcode

    def describe(self) -> str:
        """Return a safe, human-readable error description."""
        details = [self.message]

        if self.status_code is not None:
            details.append(f"HTTP status: {self.status_code}")

        if self.error_type:
            details.append(f"Error type: {self.error_type}")

        if self.error_code is not None:
            details.append(f"Facebook error code: {self.error_code}")

        if self.error_subcode is not None:
            details.append(f"Facebook error subcode: {self.error_subcode}")

        return " | ".join(details)


class PermissionSnapshot:
    """Store granted permissions and any Page-specific scope restrictions."""

    def __init__(
        self,
        granted: frozenset[str],
        granular_targets: Mapping[str, frozenset[str]],
        unrestricted_granular: frozenset[str],
    ) -> None:
        self.granted = granted
        self.granular_targets = granular_targets
        self.unrestricted_granular = unrestricted_granular

    def is_granted_for_page(self, permission: str, page_id: str) -> bool:
        """Check whether a permission is granted and applies to this Page."""
        if permission not in self.granted:
            return False

        if (
            permission in self.granular_targets
            and permission not in self.unrestricted_granular
        ):
            return page_id in self.granular_targets[permission]

        return True


def as_mapping(value: object) -> Mapping[str, object] | None:
    """Narrow an untrusted JSON value to a string-keyed mapping."""
    if not isinstance(value, Mapping):
        return None

    converted: dict[str, object] = {}

    for key, item in value.items():
        if isinstance(key, str):
            converted[key] = item

    return converted


def as_string(value: object) -> str | None:
    """Return a string value or None."""
    return value if isinstance(value, str) else None


def as_integer(value: object) -> int | None:
    """Return an integer value, excluding booleans."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value

    return None


def graph_get(
    endpoint: str,
    params: Mapping[str, str],
    version: str,
) -> Mapping[str, object]:
    """Perform a typed, timeout-protected GET request to the Graph API."""
    url = f"{GRAPH_API_BASE}/{version}/{endpoint.lstrip('/')}"
    request_url = f"{url}?{urlencode(params)}"

    request = Request(
        request_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Facebook-Page-Token-Checker/1.0",
        },
        method="GET",
    )

    try:
        with urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            status_code = response.status
            response_body = response.read()

    except HTTPError as exc:
        status_code = exc.code
        response_body = exc.read()
        exc.close()

    except (URLError, TimeoutError, OSError) as exc:
        raise GraphAPIError(f"Network request failed ({type(exc).__name__}).") from exc

    try:
        decoded_body = response_body.decode("utf-8")
        parsed_response: object = json.loads(decoded_body)

    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GraphAPIError(
            "Facebook returned a response that could not be parsed as JSON.",
            status_code=status_code,
        ) from exc

    payload = as_mapping(parsed_response)

    if payload is None:
        raise GraphAPIError(
            "Facebook returned a JSON response that was not an object.",
            status_code=status_code,
        )

    api_error = as_mapping(payload.get("error"))

    if api_error is not None:
        raise GraphAPIError(
            as_string(api_error.get("message")) or "Graph API request failed.",
            status_code=status_code,
            error_type=as_string(api_error.get("type")),
            error_code=as_integer(api_error.get("code")),
            error_subcode=as_integer(api_error.get("error_subcode")),
        )

    if not 200 <= status_code < 300:
        raise GraphAPIError(
            "Graph API request failed with an HTTP error.",
            status_code=status_code,
        )

    return payload


def get_app_access_token() -> str | None:
    """
    Read an app access token or construct one from the app ID and secret.

    The app access token must belong to the app that issued FB_PAGE_TOKEN.
    """
    app_access_token = os.getenv("FB_APP_ACCESS_TOKEN", "").strip()

    if app_access_token:
        return app_access_token

    app_id = os.getenv("FB_APP_ID", "").strip()
    app_secret = os.getenv("FB_APP_SECRET", "").strip()

    if app_id and app_secret:
        return f"{app_id}|{app_secret}"

    return None


def collect_permissions(
    debug_data: Mapping[str, object],
) -> PermissionSnapshot | None:
    """Extract permissions and granular Page-target restrictions."""
    granted: set[str] = set()
    granular_targets: dict[str, set[str]] = {}
    unrestricted_granular: set[str] = set()
    found_permission_data = False

    raw_scopes = debug_data.get("scopes")

    if isinstance(raw_scopes, list):
        found_permission_data = True

        for item in raw_scopes:
            permission = as_string(item)

            if permission:
                granted.add(permission)

    raw_granular_scopes = debug_data.get("granular_scopes")

    if isinstance(raw_granular_scopes, list):
        found_permission_data = True

        for item in raw_granular_scopes:
            granular_scope = as_mapping(item)

            if granular_scope is None:
                continue

            permission = as_string(granular_scope.get("scope"))

            if not permission:
                continue

            granted.add(permission)

            raw_target_ids = granular_scope.get("target_ids")

            if isinstance(raw_target_ids, list):
                targets = granular_targets.setdefault(permission, set())

                for raw_target_id in raw_target_ids:
                    target_id = as_string(raw_target_id)

                    if target_id:
                        targets.add(target_id)
            else:
                unrestricted_granular.add(permission)

    if not found_permission_data:
        return None

    frozen_targets = {
        permission: frozenset(target_ids)
        for permission, target_ids in granular_targets.items()
    }

    return PermissionSnapshot(
        granted=frozenset(granted),
        granular_targets=frozen_targets,
        unrestricted_granular=frozenset(unrestricted_granular),
    )


def print_timestamp(label: str, value: object) -> None:
    """Print a Unix timestamp as UTC without assuming it is always present."""
    timestamp = as_integer(value)

    if timestamp is None:
        return

    if timestamp <= 0:
        print(f"{label}: No positive expiry timestamp reported")
        return

    try:
        formatted = datetime.fromtimestamp(
            timestamp,
            tz=UTC,
        ).isoformat()

    except (OverflowError, OSError, ValueError):
        print(f"{label}: {timestamp}")
        return

    print(f"{label}: {formatted}")


def check_page_token() -> bool:
    """Return True if the Page token is valid and has all required permissions."""
    page_token = os.getenv("FB_PAGE_TOKEN", "").strip()

    if not page_token:
        return False

    version = os.getenv(
        "FB_GRAPH_API_VERSION",
        DEFAULT_GRAPH_API_VERSION,
    ).strip()

    if re.fullmatch(r"v\d+\.\d+", version) is None:
        return False

    try:
        identity = graph_get(
            "me",
            {
                "fields": "id,name",
                "access_token": page_token,
            },
            version,
        )

        page_id = as_string(identity.get("id"))

        if not page_id:
            return False

        app_access_token = get_app_access_token()

        if not app_access_token:
            return False

        debug_response = graph_get(
            "debug_token",
            {
                "input_token": page_token,
                "access_token": app_access_token,
            },
            version,
        )

    except GraphAPIError:
        return False

    debug_data = as_mapping(debug_response.get("data"))

    if debug_data is None or debug_data.get("is_valid") is not True:
        return False

    token_type = as_string(debug_data.get("type"))

    if token_type is None or token_type.upper() != "PAGE":
        return False

    permissions = collect_permissions(debug_data)

    if permissions is None:
        return False

    return all(
        permissions.is_granted_for_page(permission, page_id)
        for permission in REQUIRED_PERMISSIONS
    )
