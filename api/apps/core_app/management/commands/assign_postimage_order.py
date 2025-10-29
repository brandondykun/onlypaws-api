from django.core.management.base import BaseCommand
from django.db import transaction
from apps.core_app.models import Post


class Command(BaseCommand):
    help = "Assigns order values to PostImages based on their ID within each Post"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        try:
            # Get all posts that have images
            posts = Post.objects.filter(images__isnull=False).distinct()
            total_posts = posts.count()
            total_images_updated = 0

            self.stdout.write(f"Found {total_posts} posts with images")

            with transaction.atomic():
                for post in posts:
                    # Get all images for this post, ordered by id (ascending)
                    images = post.images.all().order_by('id')
                    
                    if images.exists():
                        self.stdout.write(
                            f"\nProcessing Post {post.id} ({images.count()} images):"
                        )
                        
                        # Assign order based on position in the ordered queryset
                        for index, image in enumerate(images):
                            old_order = image.order
                            new_order = index
                            
                            if old_order != new_order:
                                self.stdout.write(
                                    f"  - PostImage {image.id}: order {old_order} -> {new_order}"
                                )
                                
                                if not dry_run:
                                    image.order = new_order
                                    # Use update_fields to avoid triggering save logic
                                    image.save(update_fields=['order'])
                                
                                total_images_updated += 1
                            else:
                                self.stdout.write(
                                    f"  - PostImage {image.id}: order already correct ({old_order})"
                                )

                # If dry run, rollback the transaction
                if dry_run:
                    transaction.set_rollback(True)

            # Print summary
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"\nDRY RUN COMPLETE: Would update {total_images_updated} images across {total_posts} posts"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nSuccessfully updated {total_images_updated} images across {total_posts} posts"
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error assigning PostImage order: {str(e)}")
            )
            raise

