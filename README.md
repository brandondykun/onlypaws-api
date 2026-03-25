# OnlyPaws API

<img src="docs/images/ios-dark.png" alt="Only Paws Icon" width="150" style="border-radius: 15%;"/>

<br />
<br />

_The unapologetically pet friendly social media app._

---

## Table of Contents

1. [Helper Scripts](#scripts)
2. [Running the API](#running-the-api)
3. [Restarting the API](#restarting-the-api)
4. [Shutting Down the API](#shutting-down-the-api)
5. [Running Tests](#tests)
6. [Creating Fixture for Individual Model](#creating-fixture-for-individual-model)
7. [Creating Fixtures for All Models](#creating-fixtures-for-all-models)
8. [Clear and Reload Database](#clear-and-reload-database)
9. [Flush Expired JWT Tokens](#flush-expired-jwt-tokens)
10. [Generate Image Embeddings](#generate-image-embeddings)
11. [Generate Combined Post Embeddings](#generate-combined-post-embeddings)
12. [Verify and Test HNSW Indexes](#verify-and-test-hnsw-indexes)
13. [Assign PostImage Order](#assign-postimage-order)
14. [Cleanup Orphaned Images](#cleanup-orphaned-images)
15. [Maintenance Mode](#maintenance-mode)
16. [Deploy with Maintenance](#deploy-with-maintenance)
17. [Nginx Configuration and SSL Setup](#nginx-configuration-and-ssl-setup)
18. [Image Data](#image-data)
19. [Commits](#commits)
20. [Environment Variables](#environment-variables)
21. [Dev and E2E Images](#dev-and-e2e-images)
22. [Observability (SigNoz)](#observability-signoz)

---

## Scripts

Several scripts are available to help with the development process.

[assign_postimage_order.sh](#assign-postimage-order) - Assigns order values to PostImages based on their ID within each Post.

[create_fixtures.sh](#creating-fixtures-for-all-models) - Creates fixtures for all models in the given environment.

[create_model_fixture.sh](#creating-fixture-for-individual-model) - Creates a fixture for a single model in the given environment.

[flush_expired_tokens.sh](#flush-expired-jwt-tokens) - Flushes expired JWT tokens from the database.

[load_db.sh](#clear-and-reload-database) - Clears and reloads the database with the fixtures for the given environment.

[deploy-with-maintenance.sh](#deploy-with-maintenance) - Deploys the application with automatic maintenance mode handling.

[maintenance-on.sh](#maintenance-mode) - Enables maintenance mode on the nginx reverse proxy.

[maintenance-off.sh](#maintenance-mode) - Disables maintenance mode on the nginx reverse proxy.

[maintenance-status.sh](#maintenance-mode) - Checks the current maintenance mode status.

[restart.sh](#restarting-the-api) - Restarts the API service for the given environment.

[run.sh](#running-the-api) - Starts the docker containers and runs the API in the given environment.

[stop.sh](#shutting-down-the-api) - Removes the docker containers and shuts down the API.

[start-signoz.sh](#observability-signoz) - Starts the SigNoz observability stack.

[stop-signoz.sh](#observability-signoz) - Stops the SigNoz observability stack.

[test.sh](#tests) - Runs automated test suite.


## Running the API

To start the docker containers and run the API, use the `run.sh` script followed by the environment.

```bash
# base command example
scripts/run.sh <dev|staging|test|e2e|prod>

# run the api in dev environment
scripts/run.sh dev

# run the api in e2e environment (for frontend e2e tests)
scripts/run.sh e2e

# run the api in staging environment
scripts/run.sh staging

# run the api in prod environment
scripts/run.sh prod
```

**Environment Overview:**
- **dev**: Local development environment
- **e2e**: End-to-end testing environment for running frontend e2e tests
- **test**: Backend testing environment (used internally by the test suite)
- **staging**: Pre-production environment
- **prod**: Production environment

_Note: Developers rarely need to run `scripts/run.sh test` manually as it's used by the backend test suite. For frontend e2e tests, use the e2e environment instead._


## Restarting the API

To restart the API service without stopping and starting all containers, use the `restart.sh` script followed by the environment.

```bash
# base command example
scripts/restart.sh <dev|staging|test|e2e|prod>

# restart the api in dev environment
scripts/restart.sh dev

# restart the api in e2e environment
scripts/restart.sh e2e

# restart the api in staging environment
scripts/restart.sh staging

# restart the api in prod environment
scripts/restart.sh prod
```

This script will:
- Validate the environment argument
- Check that Docker is running and Docker Compose is available
- Verify that the required configuration files exist
- Restart only the `only-paws-app` service
- Display the service status after restart
- Provide helpful error messages if any issues occur

_Note: This is more efficient than stopping and starting all services when you only need to restart the main application._


## Shutting Down the API

To stop the docker containers and shut down the API, use the `stop.sh` script followed by the environment.

```bash
# base command example
scripts/stop.sh <dev|staging|test|e2e|prod>

# stop the api in dev environment
scripts/stop.sh dev

# stop the api in e2e environment
scripts/stop.sh e2e

# stop the api in staging environment
scripts/stop.sh staging

# stop the api in prod environment
scripts/stop.sh prod
```

## Tests

### Backend Tests

Backend tests can be run with or without coverage using the following commands:

```bash
# run backend tests without coverage
scripts/test.sh

# run backend tests with coverage
scripts/test.sh coverage
# report will automatically open in browser
```
Running the test script with coverage will automatically open the coverage report in the browser.

_Note: The backend test suite uses the test environment internally. Developers don't need to manually start the API with `scripts/run.sh test` to run these tests._

### E2E Tests

For frontend end-to-end (e2e) tests, the backend API must be running in the e2e environment:

```bash
# start the api in e2e mode
scripts/run.sh e2e

# run your frontend e2e tests (from frontend repo)
# ... 

# reset the e2e database after test runs
scripts/load_db.sh e2e
```

The e2e environment provides a stable backend for frontend integration testing with fixtures that can be reset between test runs.

## Creating Fixture for Individual Model

Fixtures can only be created in dev, e2e, or staging environment.

To create a fixture for an individual model, run the following command:
```bash
# base command example
scripts/create_model_fixture.sh <dev|e2e|staging> <app_name> <model_name>

# create fixture for dev environment User model from core_app
scripts/create_model_fixture.sh dev core_app user

# create fixture for e2e environment Post model from core_app
scripts/create_model_fixture.sh e2e core_app post

# create fixture for staging environment Post model from core_app
scripts/create_model_fixture.sh staging core_app post

# create fixture for dev environment Feedback model from feedback_app
scripts/create_model_fixture.sh dev feedback_app feedback
```

## Creating Fixtures For All Models

These commands will create fixtures for all models.
Prefer using the create_model_fixture.sh script to create a fixture for an individual model if possible.
Creating fixtures can only be done in dev, e2e, or staging environment.

To create fixtures for all models, run the following command:
```bash
# base command example
scripts/create_fixtures.sh <dev|e2e|staging>

# create fixtures for dev environment
scripts/create_fixtures.sh dev

# create fixtures for e2e environment
scripts/create_fixtures.sh e2e

# create fixtures for staging environment
scripts/create_fixtures.sh staging
```


## Clear and Reload Database

These are commands to help clear and reload the DB with data for dev, e2e, or staging environment.

- The DB will first be cleared of all data.
- Then the fixtures for the given environment will be loaded into the DB from the corresponding fixtures folder (e.g., fixtures/dev, fixtures/e2e).
- This is for dev, e2e, or staging ENV only.

```bash
# base command example
scripts/load_db.sh <dev|e2e|staging>

# clear and reload dev db
scripts/load_db.sh dev

# clear and reload e2e db (useful after running frontend e2e tests)
scripts/load_db.sh e2e

# clear and reload staging db
scripts/load_db.sh staging
```

**Common Use Cases:**
- **dev**: Reset development database to a known state
- **e2e**: Reset database between frontend e2e test runs to ensure consistent test conditions
- **staging**: Refresh staging environment data


## Flush Expired JWT Tokens

This script flushes expired JWT tokens from the database. It removes expired tokens from the `OutstandingToken` and `BlacklistedToken` tables to prevent the token tables from growing indefinitely.

With token rotation enabled, every time a user refreshes their token, the old token is blacklisted. Over time, these expired blacklisted tokens accumulate in the database. Running this script periodically cleans up these expired entries.

```bash
# base command example
scripts/flush_expired_tokens.sh <dev|staging|test|e2e|prod>

# flush expired tokens in dev environment
scripts/flush_expired_tokens.sh dev

# flush expired tokens in staging environment
scripts/flush_expired_tokens.sh staging

# flush expired tokens in prod environment
scripts/flush_expired_tokens.sh prod
```

**Note:** This cleanup also runs automatically via a scheduled Celery Beat task daily at 4:00 AM UTC. Use this script for manual cleanup when needed.

**When to Use:**
- After enabling token blacklisting for the first time
- When troubleshooting database size issues related to token tables
- During maintenance windows for immediate cleanup
- To verify the scheduled task is working correctly


## Generate Image Embeddings

The image similarity search feature requires embeddings to be generated for images. Use the `generate_embeddings` management command to create embeddings for PostImage instances.

```bash
# Generate embeddings for all images that don't have them
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py generate_embeddings

# Force regenerate all embeddings (overwrites existing ones)
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py generate_embeddings --force

# Generate embeddings for a specific post
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py generate_embeddings --post-id 5

# Generate embedding for a specific image
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py generate_embeddings --image-id 10

# Process images in smaller batches (default: 50)
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py generate_embeddings --batch-size 25
```

**Options:**
- `--force`: Regenerate embeddings even if they already exist
- `--post-id <ID>`: Process images for a specific post only
- `--image-id <ID>`: Process a specific PostImage only
- `--batch-size <SIZE>`: Number of images to process in each batch (default: 50)

**Note:** Embeddings are now generated asynchronously using Celery for better performance. This command is useful for:
- Initial setup with existing images
- Regenerating embeddings with updated models
- Troubleshooting missing embeddings

### New Async Options

The `generate_embeddings` command now supports both synchronous and asynchronous processing:

```bash
# Async processing (default, recommended for large batches)
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py generate_embeddings --async

# Synchronous processing (useful for development/debugging)
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py generate_embeddings --sync
```

## Generate Combined Post Embeddings

Combined embeddings merge all image embeddings with the post caption for multimodal similarity search. These embeddings enable finding similar posts based on both visual and textual content.

**Prerequisites:** Posts must have image embeddings generated first. Run the `generate_embeddings` command before generating combined embeddings.

```bash
# Generate combined embeddings for all posts that don't have them (async, recommended)
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py generate_combined_embeddings

# Force regenerate all combined embeddings (overwrites existing ones)
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py generate_combined_embeddings --force

# Generate combined embedding for a specific post
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py generate_combined_embeddings --post-id 5

# Process in smaller batches (default: 50)
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py generate_combined_embeddings --batch-size 25

# Synchronous processing for debugging
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py generate_combined_embeddings --sync

# Increase countdown for posts with many images (gives more time for image embeddings)
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py generate_combined_embeddings --countdown 30
```

**Options:**
- `--force`: Regenerate combined embeddings even if they already exist
- `--post-id <ID>`: Process a specific post only
- `--batch-size <SIZE>`: Number of posts to process in each batch (default: 50)
- `--async`: Use Celery for asynchronous processing (default, recommended)
- `--sync`: Process synchronously for development/debugging
- `--countdown <SECONDS>`: Wait time before processing in async mode (default: 5)

**How It Works:**
1. Averages all image embeddings from the post
2. Generates a text embedding from the post caption using CLIP
3. Combines them with weighted average (70% images, 30% text)
4. L2 normalizes the result for cosine similarity search

**Common Use Cases:**
- Initial setup after implementing combined embeddings feature
- Regenerating embeddings after updating the CLIP model
- Fixing failed embeddings (use `--force` on specific post)
- When caption is updated (automatically triggered, but can be manually run)

**Note:** Combined embeddings are automatically generated when new posts are created. This command is mainly for:
- Existing posts created before the feature was added
- Posts where automatic generation failed
- Bulk regeneration after model updates

**Troubleshooting:**
- If posts fail, ensure all images have embeddings first: `generate_embeddings`
- Check that Celery workers are running: `docker logs onlypaws_celery_embeddings -f`
- Use `--sync` mode to see detailed error messages during development

## Verify and Test HNSW Indexes

HNSW (Hierarchical Navigable Small World) indexes are used to accelerate vector similarity searches for finding similar posts and images. These management commands help verify that the indexes are properly configured and performing efficiently.

### Verify HNSW Indexes

The `verify_hnsw_indexes` command checks that HNSW indexes exist, are configured correctly, and provides statistics about their usage.

```bash
# Verify HNSW indexes are properly configured
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py verify_hnsw_indexes
```

**What It Checks:**
- ✅ Verifies HNSW indexes exist in the database
- ✅ Confirms indexes are using HNSW index type
- ✅ Validates HNSW parameters (m, ef_construction) are configured
- ✅ Shows index statistics (size, usage, tuples read/fetched)
- ✅ Displays embedding counts for posts and images
- ✅ Analyzes query plan to confirm index usage in similarity searches

**Sample Output:**
```
================================================================================
HNSW INDEX VERIFICATION
================================================================================

================================================================================
CHECKING HNSW INDEXES
================================================================================

✅ Found 2 HNSW index(es):

Index: post_comb_emb_hnsw_idx
  Table: public.posts_post
  Definition: CREATE INDEX post_comb_emb_hnsw_idx ON public.posts_post USING hnsw (combined_embedding vector_cosine_ops) WITH (m='32', ef_construction='128')
  ✓ Using HNSW index type
  ✓ HNSW parameters configured

Index: postimg_emb_hnsw_idx
  Table: public.posts_postimage
  Definition: CREATE INDEX postimg_emb_hnsw_idx ON public.posts_postimage USING hnsw (embedding vector_cosine_ops) WITH (m='16', ef_construction='64')
  ✓ Using HNSW index type
  ✓ HNSW parameters configured
```

**When to Use:**
- After running migrations to confirm indexes were created
- When troubleshooting slow similarity search queries
- To verify index configuration after database changes
- To check embedding generation progress

### Test HNSW Index Performance

The `test_hnsw_performance` command measures the actual performance of similarity searches and confirms that HNSW indexes are being used efficiently.

```bash
# Test HNSW index performance (default: 3 iterations)
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py test_hnsw_performance

# Run more iterations for better averages
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py test_hnsw_performance --iterations 5

# Show detailed results including sample matches
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py test_hnsw_performance --verbose
```

**Options:**
- `--iterations <N>`: Number of test runs to average (default: 3)
- `--verbose`: Show detailed results including individual iteration times and sample results

**What It Tests:**
- 🚀 Measures query execution time over multiple iterations
- 📊 Calculates average, min, and max query times
- 🔍 Shows the query execution plan
- ✅ Confirms HNSW index is being used (not sequential scan)
- 📈 Provides performance context and recommendations

**Sample Output:**
```
================================================================================
HNSW INDEX PERFORMANCE TEST
================================================================================

Testing with Post ID: 42
Total posts with embeddings: 1250

================================================================================
PERFORMANCE TESTS
================================================================================

Query Performance:
  Average: 23.45ms
  Min: 21.12ms
  Max: 28.67ms

✅ Excellent performance!

================================================================================
QUERY EXECUTION PLAN
================================================================================

Limit  (cost=...)
  ->  Index Scan using post_comb_emb_hnsw_idx on posts_post  (cost=...)
        Order By: (combined_embedding <=> '...'::vector)
        Filter: (combined_embedding IS NOT NULL)

--------------------------------------------------------------------------------
✅ HNSW index IS being used!
```

**Performance Guidelines:**
- **< 50ms**: ✅ Excellent performance
- **50-200ms**: ✅ Good performance
- **200-1000ms**: ⚠️ Moderate performance
- **> 1000ms**: ⚠️ Slow performance - index may not be used

**Note:** For small datasets (< 1000 posts), PostgreSQL may use a sequential scan instead of the index, as it can be more efficient. The index will automatically be used at scale.

**Prerequisites:**
- Combined embeddings must be generated first (see [Generate Combined Post Embeddings](#generate-combined-post-embeddings))
- HNSW indexes must be created via migrations

## Background Processing with Celery and Redis

The application uses Celery with Redis for background processing of image embeddings. This ensures that image uploads don't block the user interface while embeddings are generated.

### Services

When running with docker-compose, the following services are automatically started:

- **redis**: Redis server for Celery message broker and result backend
- **celery-worker-default**: General purpose Celery worker
- **celery-worker-embeddings**: Specialized worker for CPU-intensive embedding tasks
- **celery-beat**: Periodic task scheduler (optional)

### Testing Celery Setup

Test that Celery is working correctly:

```bash
# Test basic Celery functionality
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py test_celery

# Test embedding task discovery
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py test_celery --test-type embedding
```

### Monitoring Tasks

View Celery worker logs:

```bash
# View embedding worker logs
docker logs onlypaws_celery_embeddings -f

# View default worker logs
docker logs onlypaws_celery_default -f
```

### Manual Task Management

You can also manually queue embedding tasks:

```bash
# Start Python shell
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py shell

# In the shell:
from apps.core_app.tasks import generate_image_embedding_task
from apps.core_app.models import PostImage

# Queue embedding for specific image
task = generate_image_embedding_task.delay(post_image_id=1)
print(f"Task ID: {task.id}")
```

## Assign PostImage Order

This script assigns order values to PostImages based on their ID within each Post. Images are ordered starting from 0 for the first image (lowest ID), 1 for the second, 2 for the third, and so on.

This is useful when:
- Setting up initial order values after adding the order field
- Fixing order values that may have become inconsistent
- Ensuring consistent ordering after data migrations

```bash
# base command example
scripts/assign_postimage_order.sh <dev|e2e|staging> [--dry-run]

# Preview changes without making them (recommended first step)
scripts/assign_postimage_order.sh dev --dry-run

# Assign order values in dev environment
scripts/assign_postimage_order.sh dev

# Assign order values in e2e environment
scripts/assign_postimage_order.sh e2e

# Preview changes in staging environment
scripts/assign_postimage_order.sh staging --dry-run

# Assign order values in staging environment
scripts/assign_postimage_order.sh staging
```

**Options:**
- `--dry-run`: Preview what changes would be made without actually updating the database

**Note:** It's recommended to run with `--dry-run` first to preview the changes before applying them.


## Cleanup Orphaned Images

This management command removes orphaned images from storage (R2/S3 or local filesystem) that are not referenced in the database or fixture files. This is useful for cleaning up files that were left behind after failed uploads, manual deletions, or other edge cases.

The command automatically detects whether you're using R2/S3 cloud storage or local filesystem storage and handles each appropriately.

```bash
# Preview orphaned images without deleting (recommended first step)
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py cleanup_orphaned_images --dry-run

# Delete orphaned images using fixture files as source of truth
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py cleanup_orphaned_images

# Delete orphaned images using database as source of truth (recommended for R2)
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py cleanup_orphaned_images --source=database

# Preview with database source
docker compose -f docker/docker-compose.yml -f docker/dev/docker-compose.override.yml run --rm only-paws-app python manage.py cleanup_orphaned_images --source=database --dry-run
```

**Options:**
- `--dry-run`: Preview what would be deleted without actually deleting files
- `--source`: Source of valid image references (default: `fixtures`)
  - `fixtures`: Uses fixture JSON files (`postimage.json`, `profileimage.json`)
  - `database`: Queries `PostImage`, `PostImageScaled`, and `ProfileImage` models directly

**Supported Storage Backends:**
- **R2/S3**: Lists objects using boto3 and deletes via S3 API
- **Local filesystem**: Scans media directory and removes files/empty directories

**What Gets Checked:**
When using `--source=database`:
- `PostImage.image` - Main processed post images
- `PostImage.original_key` - Original uploaded images (if still exists)
- `PostImageScaled.image` - Scaled image variants
- `ProfileImage.image` - Profile avatar images

**Environment Restrictions:**
This command can only be run in `dev`, `staging`, or `e2e` environments as a safety measure.

**When to Use:**
- Periodically to clean up orphaned files and save storage costs
- After bulk deletions that may have left orphaned files
- When storage costs indicate many unused files
- After recovering from failed operations that left partial uploads

**Recommendation:** Always run with `--dry-run` first to preview what would be deleted. For R2/S3 storage, prefer `--source=database` as it reflects the actual current state of the database rather than potentially outdated fixture files.


## Maintenance Mode

These scripts control maintenance mode for the nginx reverse proxy. When enabled, nginx returns a 503 Service Unavailable response for most endpoints while keeping the status endpoint accessible for health checks.

### Enable Maintenance Mode

```bash
# Enable maintenance mode with default message
scripts/maintenance-on.sh

# Enable with custom message
scripts/maintenance-on.sh -m "Upgrading database. Back in 30 minutes."

# Enable with estimated end time
scripts/maintenance-on.sh -e "2024-01-15T14:00:00Z"

# Specify a different nginx container
scripts/maintenance-on.sh -c my-nginx-container
```

**Options:**
- `-m, --message MSG`: Custom maintenance message
- `-e, --end-time TIME`: Estimated end time (ISO format)
- `-c, --container NAME`: Docker container name (default: only-paws-nginx-1)

### Disable Maintenance Mode

```bash
# Disable maintenance mode
scripts/maintenance-off.sh

# Specify a different nginx container
scripts/maintenance-off.sh -c my-nginx-container
```

**Options:**
- `-c, --container NAME`: Docker container name (default: only-paws-nginx-1)

### Check Maintenance Status

```bash
# Check current maintenance mode status
scripts/maintenance-status.sh

# Specify a different nginx container
scripts/maintenance-status.sh -c my-nginx-container
```

**Options:**
- `-c, --container NAME`: Docker container name (default: only-paws-nginx-1)

**Note:** The status endpoint `/api/v1/config/status/` remains accessible during maintenance mode for health monitoring.


## Deploy with Maintenance

This script automates the deployment process with proper maintenance mode handling. It enables maintenance mode before deployment and disables it after a successful health check.

```bash
# base command example
scripts/deploy-with-maintenance.sh <dev|staging|prod> [OPTIONS]

# Deploy to staging environment
scripts/deploy-with-maintenance.sh staging

# Deploy to production environment
scripts/deploy-with-maintenance.sh prod

# Deploy with extended health check timeout
scripts/deploy-with-maintenance.sh prod --timeout 180

# Deploy without enabling maintenance mode (for minor updates)
scripts/deploy-with-maintenance.sh staging --skip-maintenance
```

**Options:**
- `--skip-maintenance`: Skip maintenance mode (useful for minor updates that don't require downtime)
- `--timeout SECONDS`: Health check timeout in seconds (default: 120)

**Deployment Steps:**
1. Enable maintenance mode (unless `--skip-maintenance` or dev environment)
2. Stop existing containers
3. Rebuild the application
4. Start containers
5. Run health checks against the status endpoint
6. Disable maintenance mode (if health check passes)

**Note:** If the health check fails, maintenance mode remains enabled and the script exits with an error. You must manually investigate and disable maintenance mode once the issue is resolved.


## Nginx Configuration and SSL Setup

The project uses nginx as a reverse proxy with SSL/TLS support via Let's Encrypt certificates. The nginx configuration is template-based to support multiple environments and domains.

### Configuration Files

- **`nginx/templates/nginx.conf.template`** - Production configuration with HTTPS, WebSocket support, and security headers
- **`nginx/templates/init.conf.template`** - Bootstrap configuration for initial SSL certificate setup
- **`nginx/docker-entrypoint.sh`** - Startup script that processes templates with environment variables

### Quick Overview

The nginx container uses template files that are processed at startup. The `${DOMAIN}` variable is replaced with your actual domain, generating the final nginx configuration.

### Setting Up SSL for New Domains

When deploying to a new domain (production), you need to obtain SSL certificates before nginx can serve HTTPS traffic. This requires a two-stage process:

1. **Stage 1**: Use the init configuration (HTTP-only) to allow Certbot to validate your domain
2. **Stage 2**: Switch to production configuration (HTTPS) once certificates are obtained

**For complete step-by-step instructions**, see the dedicated guide:

📖 **[nginx/README.md](nginx/README.md)** - Complete SSL Setup and Configuration Guide

The guide includes:
- Detailed explanation of all configuration files
- Step-by-step SSL certificate setup process
- Certificate renewal information
- Comprehensive troubleshooting section
- Quick reference commands

## Image Data

The default image data used for testing and development is located in the `api/media/images` folder.

The images are stored using the same path as their s3 path.

The image path is constructed using the following format:
 `<user_id>/<profile_id>/<post_id>/<image_name>.webp`.


## Commits

For consistency, please use the following types when creating a commit message.
#### Commit Message Types
```text
feat:       a new feature is introduced with the changes
fix:        a bug fix has occurred
chore:      changes that do not relate to a fix or feature and don't modify src or test files (for example updating dependencies)
refactor:   refactored code that neither fixes a bug nor adds a feature
docs:       updates to documentation such as a the README or other markdown files
style:      changes that do not affect the meaning of the code, likely related to code formatting such as white-space, missing semi-colons, and so on.
test:       including new or correcting previous tests
perf:       performance improvements
ci:         continuous integration related
build:      changes that affect the build system or external dependencies
revert:     reverts a previous commit
```


## Environment Variables

Before starting the API, environment variables must be set.

Each environment folder within the docker/ folder has two .env template files, one for the django rest app and one for the database.

These template files should be copied and renamed to remove the .template extension.

```bash
# example commands to copy and rename the dev env files

# command to create dev environment django app env file
cp docker/dev/.env.dev.local.template docker/dev/.env.dev.local

# command to create dev environment db env file
cp docker/dev/.env.dev.local.db.template docker/dev/.env.dev.local.db
```

Once the files are renamed, a value must be set for each variable in the file.


## E2E Images

The images for this project are not committed to the repo and must be downloaded separately.

Images for the e2e test environment are hosted on google drive. The image folder at the link below should be downloaded and placed in a media folder inside the api folder.

To create the media folder, from the root of the project run: 

```bash
mkdir api/media
```

Then download the image folder from the following link and place it in the media folder:

https://drive.google.com/drive/folders/1sHQJn6eXsJjC9hxduzrvB46HrzoQAytC

The resulting project structure for the images directory should look like the following:

```bash
api/
  media/
    images/
      e2e/
```


## Observability (SigNoz)

The API includes optional observability via a self-hosted [SigNoz](https://signoz.io/) stack that provides traces, logs, and APM metrics. SigNoz runs as a separate Docker Compose project and communicates with the app over a shared `observability` network.

```bash
# Start SigNoz (do this before starting the app)
docker/signoz/start-signoz.sh

# Stop SigNoz (preserves data)
docker/signoz/stop-signoz.sh

# Stop SigNoz and wipe all data
docker/signoz/stop-signoz.sh -v
```

**SigNoz UI:** http://localhost:3301

Telemetry is opt-in, controlled by `OTEL_EXPORTER_OTLP_ENDPOINT` in the env file. When unset, the app runs with zero observability overhead.

For detailed setup, configuration, and debugging, see **[docker/signoz/README.md](docker/signoz/README.md)**.
