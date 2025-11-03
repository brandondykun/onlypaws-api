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
10. [Assign PostImage Order](#assign-postimage-order)
11. [Image Data](#image-data)
12. [Commits](#commits)
13. [Environment Variables](#environment-variables)
14. [Dev and Test Images](#dev-and-test-images)

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
scripts/run.sh <dev|staging|test|prod>

# run the api in dev environment
scripts/run.sh dev

# run the api in test environment
scripts/run.sh test

# run the api in staging environment
scripts/run.sh staging

# run the api in prod environment
scripts/run.sh prod
```

_Note: The test environment is not for testing the API. The testing environment should be used when running the front end integration tests._


## Restarting the API

To restart the API service without stopping and starting all containers, use the `restart.sh` script followed by the environment.

```bash
# base command example
scripts/restart.sh <dev|staging|test|prod>

# restart the api in dev environment
scripts/restart.sh dev

# restart the api in test environment
scripts/restart.sh test

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
scripts/stop.sh <dev|staging|test|prod>

# stop the api in dev environment
scripts/stop.sh dev

# stop the api in test environment
scripts/stop.sh test

# stop the api in staging environment
scripts/stop.sh staging

# stop the api in prod environment
scripts/stop.sh prod
```

## Tests

Tests can be run with or without coverage using the following commands:

```bash
# run tests without coverage
scripts/test.sh

# run tests with coverage
scripts/test.sh coverage
# report will automatically open in browser
```
Running the test script with coverage will automatically open the coverage report in the browser.

## Creating Fixture for Individual Model

Fixtures can only be created in dev, test, or staging environment.

To create a fixture for an individual model, run the following command:
```bash
# base command example
scripts/create_model_fixture.sh <dev|test|staging> <app_name> <model_name>

# create fixture for dev environment User model from core_app
scripts/create_model_fixture.sh dev core_app user

# create fixture for test environment Profile model from core_app
scripts/create_model_fixture.sh test core_app profile

# create fixture for staging environment Post model from core_app
scripts/create_model_fixture.sh staging core_app post

# create fixture for dev environment Feedback model from feedback_app
scripts/create_model_fixture.sh dev feedback_app feedback
```

## Creating Fixtures For All Models

These commands will create fixtures for all models.
Prefer using the create_model_fixture.sh script to create a fixture for an individual model if possible.
Creating fixtures can only be done in dev, test, or staging environment.

To create fixtures for all models, run the following command:
```bash
# base command example
scripts/create_fixtures.sh <dev|test|staging>

# create fixtures for dev environment
scripts/create_fixtures.sh dev

# create fixtures for test environment
scripts/create_fixtures.sh test

# create fixtures for staging environment
scripts/create_fixtures.sh staging
```


## Clear and Reload Database

These are commands to help clear and reload the DB with data for dev, test, or staging environment.

- The DB will first be cleared of all data.
- Then the fixtures for the given environment from either the fixtures/dev or fixtures/test folder will be loaded into the DB.
- This is for dev, test, or staging ENV only.

```bash
# base command example
scripts/load_db.sh <dev|test|staging>

# clear and reload dev db
scripts/load_db.sh dev

# clear and reload test db
scripts/load_db.sh test

# clear and reload staging db
scripts/load_db.sh staging
```


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
scripts/assign_postimage_order.sh <dev|test|staging> [--dry-run]

# Preview changes without making them (recommended first step)
scripts/assign_postimage_order.sh dev --dry-run

# Assign order values in dev environment
scripts/assign_postimage_order.sh dev

# Assign order values in test environment
scripts/assign_postimage_order.sh test

# Preview changes in staging environment
scripts/assign_postimage_order.sh staging --dry-run

# Assign order values in staging environment
scripts/assign_postimage_order.sh staging
```

**Options:**
- `--dry-run`: Preview what changes would be made without actually updating the database

**Note:** It's recommended to run with `--dry-run` first to preview the changes before applying them.

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


## Dev and Test Images

The images for this project are not committed to the repo and must be downloaded separately.

Images for the dev and test environments are hosted on google drive. The image folder at the link below should be downloaded and placed in a media folder inside the api folder.

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
      test/
```
