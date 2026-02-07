"""
Management command to generate scaled images for existing PostImages.

This command migrates existing images to the new scaled workflow:
- Renames existing images from image_X.webp to large_X.webp
- Creates medium (500px) and small (150px) scaled variants
- Stores scaled images in a /scaled subdirectory
"""

import logging
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image, ImageOps

from apps.posts_app.models import PostImage, PostImageScaled
from apps.core_app.storage_utils import download_file, delete_file


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Generate scaled images for PostImages that don't have them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes.",
        )
        parser.add_argument(
            "--post-id",
            type=int,
            help="Process only a specific post.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Regenerate scaled images even if they exist.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Number of images to process in each batch (default: 50).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        post_id = options.get("post_id")
        force = options["force"]
        batch_size = options["batch_size"]

        if dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN MODE ===\n"))

        # Build queryset
        queryset = PostImage.objects.select_related("post", "post__profile", "post__profile__user")
        
        if post_id:
            queryset = queryset.filter(post_id=post_id)
            self.stdout.write(f"Filtering to Post ID: {post_id}")
        
        if not force:
            # Only process images that don't have all scaled variants
            # We need MEDIUM and SMALL
            queryset = queryset.exclude(
                scaled_images__scale=PostImageScaled.Scale.MEDIUM
            ).exclude(
                scaled_images__scale=PostImageScaled.Scale.SMALL
            ).distinct()

        total_count = queryset.count()
        self.stdout.write(f"Found {total_count} PostImages to process.\n")

        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("No images need processing."))
            return

        processed_count = 0
        skipped_count = 0
        error_count = 0

        # Process in batches
        for i in range(0, total_count, batch_size):
            batch = queryset[i:i + batch_size]
            
            for post_image in batch:
                try:
                    result = self._process_post_image(post_image, dry_run, force)
                    if result == "processed":
                        processed_count += 1
                    elif result == "skipped":
                        skipped_count += 1
                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(f"Error processing PostImage {post_image.id}: {e}")
                    )

            self.stdout.write(f"Progress: {min(i + batch_size, total_count)}/{total_count}")

        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"Processed: {processed_count}"))
        self.stdout.write(f"Skipped: {skipped_count}")
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"Errors: {error_count}"))

        if dry_run:
            self.stdout.write(self.style.WARNING("\n=== DRY RUN - No changes made ==="))

    def _process_post_image(self, post_image, dry_run, force):
        """Process a single PostImage to create scaled variants."""
        
        self.stdout.write(f"\nProcessing PostImage {post_image.id} (Post {post_image.post_id}, order {post_image.order})")

        # Check if we need to process
        existing_scales = set(
            post_image.scaled_images.values_list("scale", flat=True)
        )
        needs_medium = PostImageScaled.Scale.MEDIUM not in existing_scales
        needs_small = PostImageScaled.Scale.SMALL not in existing_scales
        
        if not force and not needs_medium and not needs_small:
            self.stdout.write(f"  Skipped: Already has all scaled variants")
            return "skipped"

        # Try to get source image
        source_data = None
        source_name = None
        
        # First, try original_key if it exists
        if post_image.original_key:
            self.stdout.write(f"  Trying original_key: {post_image.original_key}")
            source_data = download_file(post_image.original_key)
            if source_data:
                source_name = "original"
                self.stdout.write(f"  Using original image")
        
        # If no original, use existing image
        if source_data is None and post_image.image and post_image.image.name:
            self.stdout.write(f"  Trying existing image: {post_image.image.name}")
            source_data = download_file(post_image.image.name)
            if source_data:
                source_name = "existing"
                self.stdout.write(f"  Using existing image")
        
        if source_data is None:
            self.stdout.write(self.style.ERROR(f"  No source image found!"))
            return "skipped"

        if dry_run:
            self.stdout.write(f"  [DRY RUN] Would create scaled images from {source_name}")
            return "processed"

        # Open and process the image
        try:
            original_image = Image.open(BytesIO(source_data))
            original_image = ImageOps.exif_transpose(original_image)
            
            if original_image.mode != "RGB":
                original_image = original_image.convert("RGB")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Failed to open image: {e}"))
            return "skipped"

        # Get aspect ratio from post
        aspect_ratio = post_image.post.aspect_ratio

        # Track old image path for cleanup
        old_image_name = post_image.image.name if post_image.image else None

        # Process and save LARGE image (1080px) - update PostImage.image
        large_image = self._crop_and_resize_image(
            original_image.copy(),
            aspect_ratio,
            PostImageScaled.SCALE_DIMENSIONS["large"]
        )
        large_buffer = BytesIO()
        large_image.save(large_buffer, "webp", optimize=True, quality=70)
        large_buffer.seek(0)
        
        # Save large image with new naming convention
        large_filename = f"large_{post_image.order}.webp"
        post_image.image.save(
            large_filename,
            ContentFile(large_buffer.getvalue()),
            save=False
        )
        self.stdout.write(f"  Created large image: {post_image.image.name}")

        # Process and save MEDIUM image (500px)
        medium_image = self._crop_and_resize_image(
            original_image.copy(),
            aspect_ratio,
            PostImageScaled.SCALE_DIMENSIONS["medium"]
        )
        medium_buffer = BytesIO()
        medium_image.save(medium_buffer, "webp", optimize=True, quality=70)
        medium_buffer.seek(0)
        
        medium_scaled, _ = PostImageScaled.objects.update_or_create(
            post_image=post_image,
            scale=PostImageScaled.Scale.MEDIUM,
            defaults={
                "width": medium_image.width,
                "height": medium_image.height,
            }
        )
        medium_scaled.image.save(
            f"medium_{post_image.order}.webp",
            ContentFile(medium_buffer.getvalue()),
            save=True
        )
        self.stdout.write(f"  Created medium image: {medium_scaled.image.name}")

        # Process and save SMALL image (150px)
        small_image = self._crop_and_resize_image(
            original_image.copy(),
            aspect_ratio,
            PostImageScaled.SCALE_DIMENSIONS["small"]
        )
        small_buffer = BytesIO()
        small_image.save(small_buffer, "webp", optimize=True, quality=70)
        small_buffer.seek(0)
        
        small_scaled, _ = PostImageScaled.objects.update_or_create(
            post_image=post_image,
            scale=PostImageScaled.Scale.SMALL,
            defaults={
                "width": small_image.width,
                "height": small_image.height,
            }
        )
        small_scaled.image.save(
            f"small_{post_image.order}.webp",
            ContentFile(small_buffer.getvalue()),
            save=True
        )
        self.stdout.write(f"  Created small image: {small_scaled.image.name}")

        # Save PostImage with updated image field
        post_image.save(update_fields=["image"])

        # Delete old image if it had a different name
        if old_image_name and old_image_name != post_image.image.name:
            if delete_file(old_image_name):
                self.stdout.write(f"  Deleted old image: {old_image_name}")
            else:
                self.stdout.write(self.style.WARNING(f"  Failed to delete old image: {old_image_name}"))

        # Delete original if we used it and it exists
        if source_name == "original" and post_image.original_key:
            if delete_file(post_image.original_key):
                self.stdout.write(f"  Deleted original: {post_image.original_key}")
                post_image.original_key = None
                post_image.save(update_fields=["original_key"])

        self.stdout.write(self.style.SUCCESS(f"  Successfully processed PostImage {post_image.id}"))
        return "processed"

    def _crop_and_resize_image(self, img, aspect_ratio, base_width):
        """Crop and resize image to target aspect ratio and dimensions."""
        width, height = img.size

        # Parse aspect ratio
        w_ratio, h_ratio = map(int, aspect_ratio.split(':'))
        target_ratio = w_ratio / h_ratio

        # Calculate current ratio
        current_ratio = width / height

        # Determine crop dimensions
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

        # Calculate target dimensions
        target_width = base_width
        target_height = int(base_width / target_ratio)

        # Resize if image is larger than target
        current_width, current_height = img.size
        if current_width > target_width:
            img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

        return img
