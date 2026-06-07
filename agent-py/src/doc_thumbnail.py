"""Redacted document thumbnails for the firm dashboard (Enhancement H).

The lawyer wants to confirm the parse matches the source document — but the raw
frame contains PII (face, signature, address). We produce a small, heavily
blurred thumbnail: the document's layout/shape is recognizable enough to sanity-
check the parse, while text and faces are not legible.

This is blur-based redaction (downscale + Gaussian blur), not CV region
detection — cheap, dependency-light (Pillow), and keeps the heavy raw frame off
the dashboard. A production version would add face/text-region masking.
"""

from __future__ import annotations

import base64
import io
import logging

logger = logging.getLogger("doc_thumbnail")

THUMB_WIDTH = 280
BLUR_RADIUS = 9
JPEG_QUALITY = 55


def make_redacted_thumbnail(image_base64: str) -> str | None:
    """Return a downscaled, blurred ``data:image/jpeg;base64,...`` URL, or None."""
    raw = (image_base64 or "").split(",", 1)[-1]
    if not raw:
        return None
    try:
        from PIL import Image, ImageFilter

        image = Image.open(io.BytesIO(base64.b64decode(raw))).convert("RGB")
        if image.width > THUMB_WIDTH:
            height = max(1, round(image.height * THUMB_WIDTH / image.width))
            image = image.resize((THUMB_WIDTH, height))
        image = image.filter(ImageFilter.GaussianBlur(BLUR_RADIUS))
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=JPEG_QUALITY)
        encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception:
        logger.exception("Failed to build redacted thumbnail")
        return None
