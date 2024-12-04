from django.db import models

from django.db import models
from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from PIL import Image, ImageOps
from django.core.files import File
from io import BytesIO


class UserManager(BaseUserManager):
    """Manager for users."""

    def create_user(self, email, password=None, **extra_fields):
        """Create, save and return new user."""
        if not email:
            raise ValueError("User must have an email address.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password):
        """Create and return new superuser."""
        user = self.create_user(email, password)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)

        return user


class User(AbstractBaseUser, PermissionsMixin):
    """User in the system."""

    email = models.EmailField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"

    def __str__(self):
        return self.email


class PetType(models.Model):
    """Types of pet."""

    name = models.CharField(max_length=64, unique=True)

    def __str__(self):
        return self.name


class Profile(models.Model):
    """Profile for each user."""

    username = models.CharField(max_length=32, unique=True)
    about = models.CharField(max_length=1000, blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profiles"
    )
    name = models.CharField(max_length=64, default="", blank=True)
    pet_type = models.ForeignKey(
        PetType, on_delete=models.SET_NULL, null=True, related_name="type", blank=True
    )
    breed = models.CharField(max_length=64, null=True, default=None, blank=True)

    def __str__(self):
        return self.username


class ProfileImage(models.Model):
    profile = models.OneToOneField(
        Profile, on_delete=models.CASCADE, related_name="image"
    )
    image = models.ImageField(upload_to="images")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.image = self._resize_image(self.image)
        super().save(*args, **kwargs)

    def _resize_image(self, image):
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
        # resize image to 1080 x 1080 if it is larger than 1080
        if width > 1080:
            img = img.resize((1080, 1080))

        output = BytesIO()
        img.save(output, "webp", optimize=True)

        name_of_file = image.name.split(".")[0] + ".webp"
        return File(output, name=name_of_file)


class Post(models.Model):
    """Post with image and text."""

    caption = models.CharField(max_length=128)
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="posts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.caption


class PostImage(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="images")
    is_main = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        self.image = self._resize_image(self.image)
        super().save(*args, **kwargs)

    def _resize_image(self, image):
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
        # resize image to 1080 x 1080 if it is larger than 1080
        if width > 1080:
            img = img.resize((1080, 1080))

        output = BytesIO()
        img.save(output, "webp", optimize=True)

        name_of_file = image.name.split(".")[0] + ".webp"
        return File(output, name=name_of_file)


class Like(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="likes")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    liked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.profile} likes {self.post}"

    class Meta:
        unique_together = (("profile", "post"),)


class Comment(models.Model):
    text = models.CharField(max_length=1000)
    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="comments"
    )
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.text


class Follow(models.Model):
    followed = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="following"
    )
    followed_by = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="followers"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.followed_by.username} follows {self.followed.username}"

    class Meta:
        unique_together = (("followed", "followed_by"),)


class CommentLike(models.Model):
    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="comment_likes"
    )
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="likes")
    liked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.profile} likes {self.comment}"

    class Meta:
        unique_together = (("profile", "comment"),)
