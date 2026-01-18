import json
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Removes orphaned images from the media folder that are not referenced in fixture files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting files.",
        )

    def handle(self, *args, **options):
        environment = os.environ.get("DJANGO_ENV")
        dry_run = options["dry_run"]

        # Only allow this command in dev, staging, or e2e environments
        if environment not in ("dev", "staging", "e2e"):
            self.stdout.write(
                self.style.ERROR(
                    "This command can only be run in a staging, e2e or local dev environment!"
                )
            )
            return

        # Determine fixture path based on environment
        fixture_dir = Path(settings.BASE_DIR) / "fixtures" / environment

        # Collect all valid image paths from fixtures
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

        # Find the media images directory for this environment
        # Image paths in fixtures are like: images/dev/1/1/1/image_0.webp
        # The actual file would be at: MEDIA_ROOT/images/dev/1/1/1/image_0.webp
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

        # Find orphaned images (on disk but not in fixtures)
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
        """Remove empty directories recursively."""
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
