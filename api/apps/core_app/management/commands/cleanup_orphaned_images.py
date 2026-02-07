import json
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.core_app.storage_utils import (
    is_s3_configured,
    get_s3_client,
    delete_s3_object,
)


class Command(BaseCommand):
    help = "Removes orphaned images from storage that are not referenced in fixture files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting files.",
        )
        parser.add_argument(
            "--source",
            choices=["fixtures", "database"],
            default="fixtures",
            help="Source of valid images: 'fixtures' (default) or 'database'.",
        )

    def handle(self, *args, **options):
        environment = os.environ.get("DJANGO_ENV")
        dry_run = options["dry_run"]
        source = options["source"]

        # Only allow this command in dev, staging, or e2e environments
        if environment not in ("dev", "staging", "e2e"):
            self.stdout.write(
                self.style.ERROR(
                    "This command can only be run in a staging, e2e or local dev environment!"
                )
            )
            return

        # Collect valid image paths from the specified source
        if source == "database":
            valid_images = self._get_valid_images_from_database()
        else:
            valid_images = self._get_valid_images_from_fixtures(environment)

        if not valid_images:
            self.stdout.write(
                self.style.WARNING("No valid images found in source. Aborting to prevent accidental deletion.")
            )
            return

        # Check if using R2/S3 or local storage
        if is_s3_configured():
            self._cleanup_s3_storage(environment, valid_images, dry_run)
        else:
            self._cleanup_local_storage(environment, valid_images, dry_run)

    def _get_valid_images_from_fixtures(self, environment):
        """Collect valid image paths from fixture files."""
        fixture_dir = Path(settings.BASE_DIR) / "fixtures" / environment
        valid_images = set()

        # Load postimage.json
        postimage_path = fixture_dir / "postimage.json"
        if postimage_path.exists():
            with open(postimage_path, "r") as f:
                postimages = json.load(f)
                for item in postimages:
                    image_path = item.get("fields", {}).get("image")
                    if image_path:
                        valid_images.add(image_path)
            self.stdout.write(f"Found {len(valid_images)} post images in fixtures.")

        # Load profileimage.json
        profileimage_path = fixture_dir / "profileimage.json"
        if profileimage_path.exists():
            with open(profileimage_path, "r") as f:
                profileimages = json.load(f)
                for item in profileimages:
                    image_path = item.get("fields", {}).get("image")
                    if image_path:
                        valid_images.add(image_path)
            self.stdout.write(
                f"Total valid images after adding profile images: {len(valid_images)}"
            )

        return valid_images

    def _get_valid_images_from_database(self):
        """Collect valid image paths from database models."""
        from apps.posts_app.models import PostImage, PostImageScaled
        from apps.profile_app.models import ProfileImage

        valid_images = set()

        # Get all PostImage paths
        for post_image in PostImage.objects.exclude(image="").exclude(image__isnull=True):
            if post_image.image and post_image.image.name:
                valid_images.add(post_image.image.name)
            # Also include original_key if it exists (shouldn't normally, but just in case)
            if post_image.original_key:
                valid_images.add(post_image.original_key)

        self.stdout.write(f"Found {len(valid_images)} post images in database.")

        # Get all PostImageScaled paths
        scaled_count = 0
        for scaled_image in PostImageScaled.objects.exclude(image="").exclude(image__isnull=True):
            if scaled_image.image and scaled_image.image.name:
                valid_images.add(scaled_image.image.name)
                scaled_count += 1

        self.stdout.write(f"Found {scaled_count} scaled images in database.")

        # Get all ProfileImage paths
        profile_count = 0
        for profile_image in ProfileImage.objects.exclude(image="").exclude(image__isnull=True):
            if profile_image.image and profile_image.image.name:
                valid_images.add(profile_image.image.name)
                profile_count += 1

        self.stdout.write(f"Found {profile_count} profile images in database.")
        self.stdout.write(f"Total valid images: {len(valid_images)}")

        return valid_images

    def _cleanup_s3_storage(self, environment, valid_images, dry_run):
        """Clean up orphaned images from S3/R2 storage."""
        client = get_s3_client()
        if not client:
            self.stdout.write(
                self.style.ERROR("S3 client not configured. Cannot cleanup R2 storage.")
            )
            return

        bucket = os.environ.get("AWS_STORAGE_BUCKET_NAME")
        if not bucket:
            self.stdout.write(
                self.style.ERROR("AWS_STORAGE_BUCKET_NAME not configured.")
            )
            return

        # List all objects in the images/{environment}/ prefix
        prefix = f"images/{environment}/"
        storage_images = set()

        self.stdout.write(f"Listing objects in R2 bucket with prefix: {prefix}")

        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                # Skip directories (keys ending with /)
                if not key.endswith("/"):
                    storage_images.add(key)

        self.stdout.write(f"Found {len(storage_images)} images in R2 storage.")

        # Find orphaned images (in storage but not in valid set)
        orphaned_images = storage_images - valid_images

        if not orphaned_images:
            self.stdout.write(self.style.SUCCESS("No orphaned images found!"))
            return

        self.stdout.write(f"Found {len(orphaned_images)} orphaned images to delete:")

        deleted_count = 0
        for orphan in sorted(orphaned_images):
            if dry_run:
                self.stdout.write(f"  [DRY RUN] Would delete: {orphan}")
            else:
                if delete_s3_object(orphan):
                    self.stdout.write(f"  Deleted: {orphan}")
                    deleted_count += 1
                else:
                    self.stdout.write(
                        self.style.ERROR(f"  Failed to delete: {orphan}")
                    )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\n[DRY RUN] Would have deleted {len(orphaned_images)} orphaned images."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSuccessfully deleted {deleted_count} orphaned images from R2."
                )
            )

    def _cleanup_local_storage(self, environment, valid_images, dry_run):
        """Clean up orphaned images from local filesystem storage."""
        media_root = Path(settings.MEDIA_ROOT)
        images_dir = media_root / "images" / environment

        if not images_dir.exists():
            self.stdout.write(
                self.style.WARNING(f"Images directory does not exist: {images_dir}")
            )
            return

        # Find all image files on disk
        disk_images = set()
        for image_file in images_dir.rglob("*"):
            if image_file.is_file():
                # Convert absolute path to relative path matching fixture format
                relative_path = image_file.relative_to(media_root)
                disk_images.add(str(relative_path))

        self.stdout.write(f"Found {len(disk_images)} images on disk.")

        # Find orphaned images (on disk but not in valid set)
        orphaned_images = disk_images - valid_images

        if not orphaned_images:
            self.stdout.write(self.style.SUCCESS("No orphaned images found!"))
            return

        self.stdout.write(f"Found {len(orphaned_images)} orphaned images to delete:")

        deleted_count = 0
        for orphan in sorted(orphaned_images):
            full_path = media_root / orphan
            if dry_run:
                self.stdout.write(f"  [DRY RUN] Would delete: {orphan}")
            else:
                try:
                    full_path.unlink()
                    self.stdout.write(f"  Deleted: {orphan}")
                    deleted_count += 1
                except OSError as e:
                    self.stdout.write(
                        self.style.ERROR(f"  Failed to delete {orphan}: {e}")
                    )

        # Clean up empty directories
        if not dry_run:
            self._cleanup_empty_dirs(images_dir)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\n[DRY RUN] Would have deleted {len(orphaned_images)} orphaned images."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSuccessfully deleted {deleted_count} orphaned images."
                )
            )

    def _cleanup_empty_dirs(self, root_dir: Path):
        """Remove empty directories recursively (local storage only)."""
        empty_dirs_removed = 0
        # Walk bottom-up to remove empty directories
        for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
            dir_path = Path(dirpath)
            # Skip the root directory itself
            if dir_path == root_dir:
                continue
            # Check if directory is empty (no files and no subdirectories)
            if not any(dir_path.iterdir()):
                try:
                    dir_path.rmdir()
                    empty_dirs_removed += 1
                    self.stdout.write(f"  Removed empty directory: {dir_path}")
                except OSError:
                    pass

        if empty_dirs_removed > 0:
            self.stdout.write(f"Removed {empty_dirs_removed} empty directories.")
