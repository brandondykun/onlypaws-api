"""
Management command to test HNSW index performance for vector similarity search.

Usage:
    python manage.py test_hnsw_performance
    python manage.py test_hnsw_performance --iterations 5
    python manage.py test_hnsw_performance --verbose
"""
import time
from django.core.management.base import BaseCommand
from django.db import connection
from apps.posts_app.models import Post
from pgvector.django import CosineDistance


class Command(BaseCommand):
    help = "Test HNSW index performance for similarity search queries"

    def add_arguments(self, parser):
        parser.add_argument(
            '--iterations',
            type=int,
            default=3,
            help='Number of test iterations to run (default: 3)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed results',
        )

    def handle(self, *args, **options):
        iterations = options['iterations']
        verbose = options['verbose']
        
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("HNSW INDEX PERFORMANCE TEST"))
        self.stdout.write("=" * 80 + "\n")
        
        # Find a test post
        test_post = Post.objects.filter(combined_embedding__isnull=False).first()
        
        if not test_post:
            self.stdout.write(self.style.ERROR(
                "❌ No posts with embeddings found!"
            ))
            self.stdout.write("Generate embeddings first:")
            self.stdout.write("  python manage.py generate_combined_embeddings")
            return
        
        self.stdout.write(self.style.SUCCESS(
            f"Testing with Post ID: {test_post.id}"
        ))
        
        post_count = Post.objects.filter(combined_embedding__isnull=False).count()
        self.stdout.write(f"Total posts with embeddings: {post_count}\n")
        
        # Build similarity query
        queryset = self.build_similarity_query(test_post)
        
        # Run performance tests
        self.run_performance_tests(queryset, iterations, verbose)
        
        # Show query plan
        self.show_query_plan(queryset)
        
        # Show sample results
        if verbose:
            self.show_sample_results(queryset)
        
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("TEST COMPLETE"))
        self.stdout.write("=" * 80 + "\n")

    def build_similarity_query(self, test_post):
        """Build a similarity search query."""
        return (
            Post.objects.filter(combined_embedding__isnull=False)
            .exclude(id=test_post.id)
            .annotate(
                distance=CosineDistance(
                    "combined_embedding", 
                    test_post.combined_embedding
                )
            )
            .order_by("distance")[:10]
        )

    def run_performance_tests(self, queryset, iterations, verbose):
        """Run performance tests multiple times."""
        self.stdout.write("=" * 80)
        self.stdout.write("PERFORMANCE TESTS")
        self.stdout.write("=" * 80 + "\n")
        
        times = []
        
        for i in range(iterations):
            start = time.time()
            results = list(queryset)
            elapsed = (time.time() - start) * 1000  # Convert to ms
            times.append(elapsed)
            
            if verbose:
                self.stdout.write(
                    f"  Iteration {i+1}: {elapsed:.2f}ms ({len(results)} results)"
                )
        
        # Calculate statistics
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Query Performance:"))
        self.stdout.write(f"  Average: {avg_time:.2f}ms")
        self.stdout.write(f"  Min: {min_time:.2f}ms")
        self.stdout.write(f"  Max: {max_time:.2f}ms")
        
        # Provide context
        self.stdout.write("")
        if avg_time < 50:
            self.stdout.write(self.style.SUCCESS("✅ Excellent performance!"))
        elif avg_time < 200:
            self.stdout.write(self.style.SUCCESS("✅ Good performance"))
        elif avg_time < 1000:
            self.stdout.write(self.style.WARNING("⚠️  Moderate performance"))
        else:
            self.stdout.write(self.style.WARNING("⚠️  Slow performance - index may not be used"))

    def show_query_plan(self, queryset):
        """Show the query execution plan."""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("QUERY EXECUTION PLAN")
        self.stdout.write("=" * 80 + "\n")
        
        with connection.cursor() as cursor:
            # Get the query with proper SQL compilation and parameters
            sql, params = queryset.query.sql_with_params()
            cursor.execute(f"EXPLAIN (FORMAT TEXT, ANALYZE FALSE) {sql}", params)
            plan = cursor.fetchall()
            
            uses_hnsw = False
            uses_index = False
            
            for row in plan:
                line = row[0]
                self.stdout.write(line)
                
                if 'hnsw' in line.lower() or 'post_comb_emb_hnsw_idx' in line:
                    uses_hnsw = True
                    uses_index = True
                elif 'Index Scan' in line or 'Bitmap' in line:
                    uses_index = True
            
            self.stdout.write("\n" + "-" * 80)
            
            if uses_hnsw:
                self.stdout.write(self.style.SUCCESS("✅ HNSW index IS being used!"))
            elif uses_index:
                self.stdout.write(self.style.WARNING(
                    "⚠️  Using an index, but not the HNSW index"
                ))
            else:
                self.stdout.write(self.style.WARNING("❌ Using sequential scan"))
                
                # Check dataset size
                post_count = Post.objects.filter(combined_embedding__isnull=False).count()
                if post_count < 1000:
                    self.stdout.write(
                        f"   Note: Only {post_count} posts - index may not be used for small datasets"
                    )
                    self.stdout.write("   PostgreSQL automatically uses indexes at scale (1000+ rows)")

    def show_sample_results(self, queryset):
        """Show sample results from the query."""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("SAMPLE RESULTS")
        self.stdout.write("=" * 80 + "\n")
        
        results = list(queryset[:5])
        
        if results:
            self.stdout.write("Top 5 similar posts:\n")
            for i, post in enumerate(results, 1):
                distance = getattr(post, 'distance', None)
                similarity = (1 - distance / 2) * 100 if distance is not None else 0
                self.stdout.write(
                    f"  {i}. Post {post.id} - Distance: {distance:.4f} "
                    f"(~{similarity:.1f}% similar)"
                )
        else:
            self.stdout.write(self.style.WARNING("No similar posts found"))

