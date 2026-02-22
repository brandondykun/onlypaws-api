"""
Management command to migrate existing image objects to the new public_id-based key convention.

Uses R2/S3 storage. Run after backfilling public_id on all models.
Copies each object from its current key to the new key and updates the model's image field.
Use --dry-run to preview changes.
"""

from django.core.management.base import BaseCommand

from apps.core_app.storage_utils import (
    get_storage_env_prefix,
    copy_storage_object,
    storage_object_exists,
    delete_file,
)
from apps.profile_app.models import ProfileImage, ProfileImageScaled
from apps.posts_app.models import PostImage, PostImageScaled


class Command(BaseCommand):
    help = "Migrate image keys to the new public_id-based paths in R2/S3."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without copying or updating.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of records to process per model (default 100).",
        )
        parser.add_argument(
            "--delete-old",
            action="store_true",
            help="Delete the old object after successful copy (default: keep).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]
        delete_old = options["delete_old"]

        prefix = get_storage_env_prefix()

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made."))

        total_copied = 0
        total_skipped = 0
        total_errors = 0

        # ProfileImage: profiles/<public_id>/avatar_400.webp
        for obj in ProfileImage.objects.filter(image__isnull=False).exclude(image="").select_related("profile")[:batch_size]:
            old_key = obj.image.name
            if not old_key:
                continue
            new_key = f"{prefix}profiles/{obj.profile.public_id}/avatar_400.webp"
            if old_key == new_key:
                total_skipped += 1
                continue
            if not storage_object_exists(old_key):
                self.stdout.write(self.style.WARNING(f"  Source missing: {old_key}"))
                total_skipped += 1
                continue
            if dry_run:
                self.stdout.write(f"  Would copy: {old_key} -> {new_key}")
                total_copied += 1
                continue
            if copy_storage_object(old_key, new_key):
                ProfileImage.objects.filter(pk=obj.pk).update(image=new_key)
                total_copied += 1
                if delete_old:
                    delete_file(old_key)
            else:
                total_errors += 1

        # ProfileImageScaled: profiles/<public_id>/avatar_<dim>.webp
        for obj in ProfileImageScaled.objects.filter(image__isnull=False).exclude(image="").select_related("profile_image__profile")[:batch_size]:
            old_key = obj.image.name
            if not old_key:
                continue
            dim = ProfileImageScaled.SCALE_DIMENSIONS[obj.scale]
            new_key = f"{prefix}profiles/{obj.profile_image.profile.public_id}/avatar_{dim}.webp"
            if old_key == new_key:
                total_skipped += 1
                continue
            if not storage_object_exists(old_key):
                total_skipped += 1
                continue
            if dry_run:
                self.stdout.write(f"  Would copy: {old_key} -> {new_key}")
                total_copied += 1
                continue
            if copy_storage_object(old_key, new_key):
                ProfileImageScaled.objects.filter(pk=obj.pk).update(image=new_key)
                total_copied += 1
                if delete_old:
                    delete_file(old_key)
            else:
                total_errors += 1

        # PostImage: posts/<public_id>/<order>_1080.webp
        # Use sequential order per post (0, 1, 2, ...) so multiple images get unique keys
        postimage_qs = (
            PostImage.objects.filter(image__isnull=False)
            .exclude(image="")
            .select_related("post")[:batch_size]
        )
        postimage_batch = list(postimage_qs)
        post_ids = {obj.post_id for obj in postimage_batch}
        order_index = {}
        for post_id in post_ids:
            pks = list(
                PostImage.objects.filter(post_id=post_id)
                .order_by("pk")
                .values_list("pk", flat=True)
            )
            order_index[post_id] = {pk: i for i, pk in enumerate(pks)}
        for obj in postimage_batch:
            old_key = obj.image.name
            if not old_key:
                continue
            effective_order = order_index[obj.post_id][obj.pk]
            new_key = f"{prefix}posts/{obj.post.public_id}/{effective_order}_1080.webp"
            if old_key == new_key and obj.order == effective_order:
                total_skipped += 1
                continue
            if not storage_object_exists(old_key):
                total_skipped += 1
                continue
            if dry_run:
                self.stdout.write(f"  Would copy: {old_key} -> {new_key}")
                total_copied += 1
                continue
            if copy_storage_object(old_key, new_key):
                PostImage.objects.filter(pk=obj.pk).update(image=new_key, order=effective_order)
                total_copied += 1
                if delete_old:
                    delete_file(old_key)
            else:
                total_errors += 1

        # PostImageScaled: posts/<public_id>/<order>_<dim>.webp
        for obj in PostImageScaled.objects.filter(image__isnull=False).exclude(image="").select_related("post_image__post")[:batch_size]:
            old_key = obj.image.name
            if not old_key:
                continue
            dim = PostImageScaled.SCALE_DIMENSIONS[obj.scale]
            new_key = f"{prefix}posts/{obj.post_image.post.public_id}/{obj.post_image.order}_{dim}.webp"
            if old_key == new_key:
                total_skipped += 1
                continue
            if not storage_object_exists(old_key):
                total_skipped += 1
                continue
            if dry_run:
                self.stdout.write(f"  Would copy: {old_key} -> {new_key}")
                total_copied += 1
                continue
            if copy_storage_object(old_key, new_key):
                PostImageScaled.objects.filter(pk=obj.pk).update(image=new_key)
                total_copied += 1
                if delete_old:
                    delete_file(old_key)
            else:
                total_errors += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. copied={total_copied} skipped={total_skipped} errors={total_errors}"
            )
        )
