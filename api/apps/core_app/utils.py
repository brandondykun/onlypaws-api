import os

from PIL import Image, ImageOps
from django.core.files import File
from django.conf import settings

from io import BytesIO
import uuid

# Register HEIF support for iPhone images
try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass  # pillow-heif not installed, HEIC images won't be supported


ASPECT_RATIO_DIMENSIONS = {
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
}


def crop_to_aspect_ratio_and_resize(image, aspect_ratio="1:1", base_width=1080):
    """
    Crop and resize image to desired aspect ratio.
    The image is center-cropped to match the target aspect ratio.

    Args:
        image: The image file to process
        aspect_ratio: Target aspect ratio as string (e.g., "1:1", "4:5")
        base_width: The target width in pixels (default 1080)

    Returns:
        Processed image file in webp format
    """
    img = Image.open(image)
    img = ImageOps.exif_transpose(img)  # rotate the image based on EXIF data

    width, height = img.size

    # Parse aspect ratio
    w_ratio, h_ratio = map(int, aspect_ratio.split(":"))
    target_ratio = w_ratio / h_ratio  # e.g., 4/5 = 0.8 for 4:5

    # Calculate current ratio
    current_ratio = width / height

    # Determine crop dimensions
    if abs(current_ratio - target_ratio) < 0.001:
        # Already matches target ratio, no crop needed
        crop_width, crop_height = width, height
        left, top = 0, 0
    elif current_ratio > target_ratio:
        # Image is wider than target - crop left and right
        crop_height = height
        crop_width = int(height * target_ratio)
        left = (width - crop_width) / 2
        top = 0
    else:
        # Image is taller than target - crop top and bottom
        crop_width = width
        crop_height = int(width / target_ratio)
        left = 0
        top = (height - crop_height) / 2

    right = left + crop_width
    bottom = top + crop_height

    img = img.crop((left, top, right, bottom))

    # Get target dimensions - use lookup only if using default base_width
    if base_width == 1080 and aspect_ratio in ASPECT_RATIO_DIMENSIONS:
        target_width, target_height = ASPECT_RATIO_DIMENSIONS[aspect_ratio]
    else:
        target_width = base_width
        target_height = int(base_width / target_ratio)

    # Resize if image is larger than target dimensions
    current_width, current_height = img.size
    if current_width > target_width:
        img = img.resize((target_width, target_height))

    output = BytesIO()
    img.save(output, "webp", optimize=True, quality=70)

    # Use only the basename to avoid path duplication when upload_to adds prefix
    basename = os.path.basename(image.name)
    name_of_file = os.path.splitext(basename)[0] + ".webp"

    return File(output, name=name_of_file)


def generate_verification_code():
    # use a fixed verification code for e2e tests
    if os.environ.get("DJANGO_ENV") == "e2e":
        code = getattr(settings, "E2E_VERIFICATION_CODE", None)
        if code:
            return code
    # return a random verification code for other environments
    return str(uuid.uuid4())[:6]
