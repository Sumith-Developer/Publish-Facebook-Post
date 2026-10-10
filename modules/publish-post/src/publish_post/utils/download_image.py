from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import parse_qs, urlsplit

import requests
from PIL import ExifTags, Image, UnidentifiedImageError


@dataclass(frozen=True, slots=True)
class DownloadedImage:
    content: bytes
    filename: str
    mime_type: str
    image_format: str
    width: int
    height: int
    metadata: Mapping[str, object]

    @property
    def buffer(self) -> BytesIO:
        return BytesIO(self.content)


def download_google_drive_image(
    public_url: str,
    *,
    max_bytes: int = 25 * 1024 * 1024,
    timeout: float = 30,
) -> DownloadedImage:
    """Download and validate an image from a public Google Drive link."""

    parsed = urlsplit(public_url)

    if parsed.scheme != "https" or parsed.hostname != "drive.google.com":
        raise ValueError("A valid HTTPS Google Drive link is required.")

    file_id = parse_qs(parsed.query).get("id", [""])[0]

    if not file_id:
        match = re.search(r"/file/d/([^/]+)", parsed.path)
        file_id = match.group(1) if match else ""

    if not re.fullmatch(r"[A-Za-z0-9_-]+", file_id):
        raise ValueError("Could not extract a valid Google Drive file ID.")

    with requests.Session() as session:
        response = session.get(
            "https://drive.google.com/uc",
            params={"export": "download", "id": file_id},
            timeout=timeout,
            stream=True,
        )

        with response:
            response.raise_for_status()

            content = bytearray()

            for chunk in response.iter_content(64 * 1024):
                content.extend(chunk)

                if len(content) > max_bytes:
                    raise ValueError("Image exceeds the maximum allowed size.")

            content_type = response.headers.get("Content-Type", "")

    if not content:
        raise ValueError("The downloaded file is empty.")

    if "text/html" in content_type.lower():
        raise ValueError(
            "Google Drive returned a web page. Check public sharing permissions."
        )

    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()

        with Image.open(BytesIO(content)) as image:
            image.load()

            image_format = image.format
            width, height = image.size
            mime_type = Image.MIME.get(image_format or "", "")

            if not mime_type.startswith("image/"):
                raise ValueError("Unsupported image format.")

            metadata = {
                ExifTags.TAGS.get(tag, str(tag)): str(value)
                for tag, value in image.getexif().items()
            }

    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("The downloaded file is not a valid image.") from exc

    extensions = {
        "JPEG": ".jpg",
        "PNG": ".png",
        "WEBP": ".webp",
        "GIF": ".gif",
        "BMP": ".bmp",
        "TIFF": ".tiff",
        "AVIF": ".avif",
    }

    extension = extensions.get(image_format or "", ".img")

    return DownloadedImage(
        content=bytes(content),
        filename=f"{file_id}{extension}",
        mime_type=mime_type,
        image_format=image_format or "",
        width=width,
        height=height,
        metadata=metadata,
    )
