"""
Management command to verify HNSW indexes are created and configured correctly.

Usage:
    python manage.py verify_hnsw_indexes
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Verify HNSW indexes for vector similarity search are properly configured"

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("HNSW INDEX VERIFICATION"))
        self.stdout.write("=" * 80)
        
        indexes_exist = self.check_indexes()
        
        if indexes_exist:
            self.check_index_stats()
            self.count_embeddings()
            self.explain_query()
        
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("VERIFICATION COMPLETE"))
        self.stdout.write("=" * 80 + "\n")

    def check_indexes(self):
        """Check if HNSW indexes exist in the database."""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("CHECKING HNSW INDEXES")
        self.stdout.write("=" * 80 + "\n")
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE indexname IN ('post_comb_emb_hnsw_idx', 'postimg_emb_hnsw_idx')
                ORDER BY indexname;
            """)
            
            indexes = cursor.fetchall()
            
            if not indexes:
                self.stdout.write(self.style.ERROR("❌ No HNSW indexes found!"))
                self.stdout.write("\nRun migrations first: python manage.py migrate")
                return False
            
            self.stdout.write(self.style.SUCCESS(f"✅ Found {len(indexes)} HNSW index(es):\n"))
            
            for schema, table, name, definition in indexes:
                self.stdout.write(self.style.SUCCESS(f"Index: {name}"))
                self.stdout.write(f"  Table: {schema}.{table}")
                self.stdout.write(f"  Definition: {definition}")
                
                # Verify it's actually using HNSW
                if 'USING hnsw' in definition:
                    self.stdout.write(self.style.SUCCESS("  ✓ Using HNSW index type"))
                else:
                    self.stdout.write(self.style.WARNING("  ⚠ Not using HNSW index type!"))
                
                # Check for parameters (they appear as m='32' in the definition)
                if 'm=' in definition and 'ef_construction=' in definition:
                    self.stdout.write(self.style.SUCCESS("  ✓ HNSW parameters configured"))
                else:
                    self.stdout.write(self.style.WARNING("  ⚠ HNSW parameters missing"))
                
                self.stdout.write("")
            
            return True

    def check_index_stats(self):
        """Check index statistics and size."""
        self.stdout.write("=" * 80)
        self.stdout.write("INDEX STATISTICS")
        self.stdout.write("=" * 80 + "\n")
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    indexrelname as indexname,
                    pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
                    idx_scan as times_used,
                    idx_tup_read as tuples_read,
                    idx_tup_fetch as tuples_fetched
                FROM pg_stat_user_indexes
                WHERE indexrelname IN ('post_comb_emb_hnsw_idx', 'postimg_emb_hnsw_idx')
                ORDER BY indexrelname;
            """)
            
            stats = cursor.fetchall()
            
            if not stats:
                self.stdout.write(self.style.WARNING("❌ No statistics found for HNSW indexes"))
                return
            
            for name, size, scans, reads, fetches in stats:
                self.stdout.write(self.style.SUCCESS(f"Index: {name}"))
                self.stdout.write(f"  Size: {size}")
                self.stdout.write(f"  Times used: {scans or 0}")
                self.stdout.write(f"  Tuples read: {reads or 0}")
                self.stdout.write(f"  Tuples fetched: {fetches or 0}")
                self.stdout.write("")

    def count_embeddings(self):
        """Count posts and images with embeddings."""
        from apps.posts_app.models import Post, PostImage
        
        self.stdout.write("=" * 80)
        self.stdout.write("EMBEDDING STATISTICS")
        self.stdout.write("=" * 80 + "\n")
        
        post_count = Post.objects.filter(combined_embedding__isnull=False).count()
        total_posts = Post.objects.count()
        
        image_count = PostImage.objects.filter(embedding__isnull=False).count()
        total_images = PostImage.objects.count()
        
        self.stdout.write(f"Posts with embeddings: {post_count} / {total_posts}")
        self.stdout.write(f"Images with embeddings: {image_count} / {total_images}")
        
        if post_count == 0:
            self.stdout.write(self.style.WARNING(
                "\n⚠️  Warning: No posts have embeddings yet!"
            ))
            self.stdout.write("   Generate embeddings: python manage.py generate_combined_embeddings")
        
        if post_count < 1000:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️  Note: Only {post_count} posts with embeddings."
            ))
            self.stdout.write("   PostgreSQL may not use the index for small datasets.")
            self.stdout.write("   The index will be automatically used at scale (1000+ posts).")

    def explain_query(self):
        """Show query plan for similarity search to verify index usage."""
        from apps.posts_app.models import Post
        from pgvector.django import CosineDistance
        
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("QUERY PLAN ANALYSIS")
        self.stdout.write("=" * 80 + "\n")
        
        # Find a post with an embedding
        post_with_embedding = Post.objects.filter(
            combined_embedding__isnull=False
        ).first()
        
        if not post_with_embedding:
            self.stdout.write(self.style.WARNING(
                "⚠️  No posts with embeddings found. Create some first!"
            ))
            return
        
        self.stdout.write(self.style.SUCCESS(
            f"Testing with Post ID: {post_with_embedding.id}\n"
        ))
        
        # Build similarity query
        queryset = (
            Post.objects.filter(combined_embedding__isnull=False)
            .exclude(id=post_with_embedding.id)
            .annotate(
                distance=CosineDistance(
                    "combined_embedding", 
                    post_with_embedding.combined_embedding
                )
            )
            .filter(distance__lte=1.8)
            .order_by("distance")[:10]
        )
        
        with connection.cursor() as cursor:
            # Get the query with proper SQL compilation
            sql, params = queryset.query.sql_with_params()
            
            # Get query plan with parameters
            cursor.execute(f"EXPLAIN (FORMAT TEXT, ANALYZE FALSE) {sql}", params)
            plan = cursor.fetchall()
            
            self.stdout.write("Query Plan:")
            self.stdout.write("-" * 80)
            for row in plan:
                self.stdout.write(row[0])
            
            # Check if index is being used
            plan_text = '\n'.join([row[0] for row in plan])
            
            self.stdout.write("\n" + "=" * 80)
            if 'post_comb_emb_hnsw_idx' in plan_text or 'hnsw' in plan_text.lower():
                self.stdout.write(self.style.SUCCESS("✅ HNSW INDEX IS BEING USED!"))
            elif 'Index Scan' in plan_text or 'Bitmap' in plan_text:
                self.stdout.write(self.style.WARNING(
                    "⚠️  An index is being used, but might not be the HNSW index"
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    "❌ No index detected - using sequential scan"
                ))
                self.stdout.write("   This is normal for small datasets (< 1000 posts)")
            self.stdout.write("=" * 80)

