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
9. [Generate Image Embeddings](#generate-image-embeddings)
10. [Generate Combined Post Embeddings](#generate-combined-post-embeddings)
11. [Assign PostImage Order](#assign-postimage-order)
12. [Nginx Configuration and SSL Setup](#nginx-configuration-and-ssl-setup)
13. [Image Data](#image-data)
14. [Commits](#commits)
15. [Environment Variables](#environment-variables)
16. [Dev and E2E Images](#dev-and-e2e-images)

---

## Scripts

Several scripts are available to help with the development process.

[assign_postimage_order.sh](#assign-postimage-order) - Assigns order values to PostImages based on their ID within each Post.

[create_fixtures.sh](#creating-fixtures-for-all-models) - Creates fixtures for all models in the given environment.

[create_model_fixture.sh](#creating-fixture-for-individual-model) - Creates a fixture for a single model in the given environment.

[load_db.sh](#clear-and-reload-database) - Clears and reloads the database with the fixtures for the given environment.

[restart.sh](#restarting-the-api) - Restarts the API service for the given environment.

[run.sh](#running-the-api) - Starts the docker containers and runs the API in the given environment.

[stop.sh](#shutting-down-the-api) - Removes the docker containers and shuts down the API.

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


## Dev and E2E Images

The images for this project are not committed to the repo and must be downloaded separately.

Images for the dev and e2e test environments are hosted on google drive. The image folder at the link below should be downloaded and placed in a media folder inside the api folder.

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
      dev/
      e2e/
```
