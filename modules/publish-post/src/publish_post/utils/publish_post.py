import os
from typing import Any

import requests
from dotenv import load_dotenv

from .download_image import DownloadedImage

load_dotenv()


def publish_page_photo(
    message: str,
    image: DownloadedImage,
    *,
    page_id: str | None = None,
    page_access_token: str | None = None,
    api_version: str = "v26.0",
) -> dict[str, Any]:
    page_id = page_id or os.getenv("FB_PAGE_ID")
    page_access_token = page_access_token or os.getenv("FB_PAGE_TOKEN")
    api_version = os.getenv("FB_GRAPH_API_VERSION") or api_version

    if not page_id or not page_access_token:
        raise ValueError("Missing FB_PAGE_ID or FB_PAGE_TOKEN.")

    if not image.content:
        raise ValueError("Image content is empty.")

    url = f"https://graph.facebook.com/{api_version}/{page_id}/photos"

    try:
        response = requests.post(
            url,
            data={
                "message": message,
                "access_token": page_access_token,
            },
            files={
                "source": (image.filename, image.content, image.mime_type),
            },
            timeout=60,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to publish Facebook photo: {exc}") from exc

    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Facebook returned an invalid response (HTTP {response.status_code})."
        ) from exc

    if not response.ok or "error" in result:
        error = result.get("error", result)
        raise RuntimeError(
            f"Facebook Graph API error (HTTP {response.status_code}): {error}"
        )

    return result
