"""
Management command to generate scaled images for existing ProfileImages.

Creates medium (200px) and small (100px) variants from the main profile image
for ProfileImages that don't have them (e.g. migrated from legacy single-image
or created before scaled workflow). Profile images are always 1:1 aspect ratio.
"""

import logging
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image, ImageOps

from apps.profile_app.models import ProfileImage, ProfileImageScaled
from apps.core_app.storage_utils import download_file


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Generate scaled images (medium, small) for ProfileImages that don't have them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes.",
        )
        parser.add_argument(
            "--profile-id",
            type=int,
            metavar="ID",
            help="Process only the profile image for this profile ID.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Regenerate scaled images even if they already exist.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Number of profile images to process per batch (default: 50).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        profile_id = options.get("profile_id")
        force = options["force"]
        batch_size = options["batch_size"]

        if dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN MODE ===\n"))

        queryset = ProfileImage.objects.select_related("profile", "profile__user").filter(
            image__isnull=False
        )

        if profile_id:
            queryset = queryset.filter(profile_id=profile_id)
            self.stdout.write(f"Filtering to Profile ID: {profile_id}\n")

        if not force:
            queryset = queryset.exclude(
                scaled_images__scale=ProfileImageScaled.Scale.MEDIUM,
            ).exclude(
                scaled_images__scale=ProfileImageScaled.Scale.SMALL,
            ).distinct()

        total_count = queryset.count()
        self.stdout.write(f"Found {total_count} ProfileImage(s) to process.\n")

        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("No profile images need processing."))
            return

        processed_count = 0
        skipped_count = 0
        error_count = 0

        for i in range(0, total_count, batch_size):
            batch = queryset[i : i + batch_size]
            for profile_image in batch:
                try:
                    result = self._process_profile_image(profile_image, dry_run, force)
                    if result == "processed":
                        processed_count += 1
                    elif result == "skipped":
                        skipped_count += 1
                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(f"Error processing ProfileImage {profile_image.id}: {e}")
                    )
            self.stdout.write(f"Progress: {min(i + batch_size, total_count)}/{total_count}")

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"Processed: {processed_count}"))
        self.stdout.write(f"Skipped: {skipped_count}")
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"Errors: {error_count}"))

        if dry_run:
            self.stdout.write(self.style.WARNING("\n=== DRY RUN - No changes made ==="))

    def _process_profile_image(self, profile_image, dry_run, force):
        """Create medium and small scaled variants from the main profile image."""
        self.stdout.write(
            f"\nProcessing ProfileImage {profile_image.id} (Profile {profile_image.profile_id}, {profile_image.profile.username})"
        )

        existing_scales = set(
            profile_image.scaled_images.values_list("scale", flat=True)
        )
        needs_medium = ProfileImageScaled.Scale.MEDIUM not in existing_scales
        needs_small = ProfileImageScaled.Scale.SMALL not in existing_scales

        if not force and not needs_medium and not needs_small:
            self.stdout.write("  Skipped: Already has all scaled variants")
            return "skipped"

        if not profile_image.image or not profile_image.image.name:
            self.stdout.write(self.style.ERROR("  No source image found."))
            return "skipped"

        source_data = download_file(profile_image.image.name)
        if source_data is None:
            self.stdout.write(self.style.ERROR(f"  Could not read image: {profile_image.image.name}"))
            return "skipped"

        if dry_run:
            self.stdout.write(
                f"  [DRY RUN] Would create scaled images from {profile_image.image.name}"
            )
            return "processed"

        try:
            original_image = Image.open(BytesIO(source_data))
            original_image = ImageOps.exif_transpose(original_image)
            if original_image.mode != "RGB":
                original_image = original_image.convert("RGB")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Failed to open image: {e}"))
            return "skipped"

        aspect_ratio = "1:1"

        if needs_medium:
            medium_image = self._crop_and_resize(
                original_image.copy(),
                aspect_ratio,
                ProfileImageScaled.SCALE_DIMENSIONS["medium"],
            )
            medium_buffer = BytesIO()
            medium_image.save(medium_buffer, "webp", optimize=True, quality=70)
            medium_buffer.seek(0)
            medium_scaled, _ = ProfileImageScaled.objects.update_or_create(
                profile_image=profile_image,
                scale=ProfileImageScaled.Scale.MEDIUM,
                defaults={
                    "width": medium_image.width,
                    "height": medium_image.height,
                },
            )
            medium_scaled.image.save(
                "medium.webp",
                ContentFile(medium_buffer.getvalue()),
                save=True,
            )
            self.stdout.write(f"  Created medium image: {medium_scaled.image.name}")

        if needs_small:
            small_image = self._crop_and_resize(
                original_image.copy(),
                aspect_ratio,
                ProfileImageScaled.SCALE_DIMENSIONS["small"],
            )
            small_buffer = BytesIO()
            small_image.save(small_buffer, "webp", optimize=True, quality=70)
            small_buffer.seek(0)
            small_scaled, _ = ProfileImageScaled.objects.update_or_create(
                profile_image=profile_image,
                scale=ProfileImageScaled.Scale.SMALL,
                defaults={
                    "width": small_image.width,
                    "height": small_image.height,
                },
            )
            small_scaled.image.save(
                "small.webp",
                ContentFile(small_buffer.getvalue()),
                save=True,
            )
            self.stdout.write(f"  Created small image: {small_scaled.image.name}")

        self.stdout.write(self.style.SUCCESS(f"  Successfully processed ProfileImage {profile_image.id}"))
        return "processed"

    def _crop_and_resize(self, img, aspect_ratio, base_width):
        """Crop and resize image to 1:1 aspect ratio and target width."""
        width, height = img.size
        w_ratio, h_ratio = map(int, aspect_ratio.split(":"))
        target_ratio = w_ratio / h_ratio
        current_ratio = width / height

        if abs(current_ratio - target_ratio) < 0.001:
            crop_width, crop_height = width, height
            left, top = 0, 0
        elif current_ratio > target_ratio:
            crop_height = height
            crop_width = int(height * target_ratio)
            left = (width - crop_width) / 2
            top = 0
        else:
            crop_width = width
            crop_height = int(width / target_ratio)
            left = 0
            top = (height - crop_height) / 2

        right = left + crop_width
        bottom = top + crop_height
        img = img.crop((left, top, right, bottom))

        target_height = int(base_width / target_ratio)
        current_width, current_height = img.size
        if current_width > base_width:
            img = img.resize((base_width, target_height), Image.Resampling.LANCZOS)
        return img
