from PIL import Image, ImageOps
from django.core.files import File
from io import BytesIO


def crop_square_and_resize(image, image_size=1080):
    """
    Crop and resize image to desired image size.
    The image is cropped to into a square that is centered on the photo.
    If the image is taller than it is wide, part of the top and bottom is cropped.
    If the image is wider than it is tall, part of the left and right is cropped.
    """
    img = Image.open(image)
    img = ImageOps.exif_transpose(img)  # rotate the image

    width, height = img.size  # Get dimensions

    if height > width:
        left = 0
        right = width
        top = (height / 2) - (width / 2)
        bottom = top + width
    else:
        top = 0
        bottom = height
        left = (width / 2) - (height / 2)
        right = left + height

    img = img.crop((left, top, right, bottom))

    width, height = img.size
    # resize image if it is larger than desired image size
    if width > image_size:
        img = img.resize((image_size, image_size))

    output = BytesIO()
    img.save(output, "webp", optimize=True, quality=70)

    name_of_file = image.name.split(".")[0] + ".webp"

    return File(output, name=name_of_file)
