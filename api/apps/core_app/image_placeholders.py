"""
Utilities for generating lightweight image placeholders.
"""

import logging
import base64
from io import BytesIO
from typing import Optional

import blurhash
from PIL import Image, ImageOps

from apps.core_app.storage_utils import download_file

logger = logging.getLogger(__name__)

# Number of cosine basis "cells" per axis. More cells = finer positional color
# detail. Kept symmetric because posts are only ever 1:1 or 4:5 (never landscape),
# so the taller portrait axis should get at least as many cells as the width.
# 7x7 encodes to a 102-char string, which fits the 128-char model field.
BLURHASH_COMPONENTS_X = 7
BLURHASH_COMPONENTS_Y = 7
# Source is downscaled to this before encoding. It must stay large enough that
# each component is well sampled (roughly >=10px/component); at 96px that's
# ~14px per cell for 7 components. Too small under-samples the higher-frequency
# coefficients that carry the positional detail. Encoding stays a few ms.
BLURHASH_MAX_SOURCE_SIZE = 96


def generate_blurhash_from_image(image: Image.Image) -> str:
    """
    Generate a BlurHash string from a PIL image.

    The source image is copied and downscaled in memory before encoding so
    encoding stays cheap and no temporary placeholder image is persisted.
    """
    placeholder_image = ImageOps.exif_transpose(image.copy())

    if placeholder_image.mode != "RGB":
        placeholder_image = placeholder_image.convert("RGB")

    placeholder_image.thumbnail(
        (BLURHASH_MAX_SOURCE_SIZE, BLURHASH_MAX_SOURCE_SIZE),
        Image.Resampling.LANCZOS,
    )

    return blurhash.encode(
        placeholder_image,
        x_components=BLURHASH_COMPONENTS_X,
        y_components=BLURHASH_COMPONENTS_Y,
    )


def blurhash_to_data_uri(post_blurhash: str, width: int = 64, height: int = 64) -> Optional[str]:
    """Decode a BlurHash string to a PNG data URI for admin previews."""
    try:
        image = blurhash.decode(post_blurhash, width, height)
        output = BytesIO()
        image.save(output, "PNG")
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except Exception:
        logger.exception("Failed to decode blurhash for preview")
        return None


def generate_blurhash_for_post_image(post_image) -> Optional[str]:
    """
    Generate a BlurHash string for a stored PostImage.

    Prefer the SMALL scaled variant because it has already been cropped to the
    post's display aspect ratio, then fall back to the main processed image.
    """
    image_key = _get_best_post_image_key(post_image)
    if not image_key:
        return None

    image_data = download_file(image_key)
    if image_data is None:
        logger.warning(
            "Unable to download image for blurhash generation: PostImage %s, key %s",
            post_image.id,
            image_key,
        )
        return None

    try:
        with Image.open(BytesIO(image_data)) as image:
            return generate_blurhash_from_image(image)
    except Exception:
        logger.exception(
            "Failed to generate blurhash for PostImage %s from key %s",
            post_image.id,
            image_key,
        )
        return None


def _get_best_post_image_key(post_image) -> Optional[str]:
    """Return the preferred stored image key for generating an image blurhash."""
    from apps.posts_app.models import PostImageScaled

    for scaled_image in post_image.scaled_images.all():
        if (
            scaled_image.scale == PostImageScaled.Scale.SMALL
            and scaled_image.image
            and scaled_image.image.name
        ):
            return scaled_image.image.name

    if post_image.image and post_image.image.name:
        return post_image.image.name

    return None
