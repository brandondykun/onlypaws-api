# OnlyPaws API

1. [Helper Scripts](#scripts)
2. [Running the API](#running-the-api)
3. [Shutting Down the API](#shutting-down-the-api)
4. [Running Tests](#tests)
5. [Creating Fixture for Individual Model](#creating-fixture-for-individual-model)
6. [Creating Fixtures for All Models](#creating-fixtures-for-all-models)
7. [Clear and Reload Database](#clear-and-reload-database)
8. [Image Data](#image-data)
9. [Commits](#commits)
10. [Environment Variables](#environment-variables)


## Scripts

Several scripts are available to help with the development process.

[create_fixtures.sh](#creating-fixtures-for-all-models) - Creates fixtures for all models in the given environment.
[create_model_fixture.sh](#creating-fixture-for-individual-model) - Creates a fixture for a single model in the given environment.
[load_db.sh](#clear-and-reload-database) - Clears and reloads the database with the fixtures for the given environment.
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

Fixtures can only be created in dev or test environment.

To create a fixture for an individual model, run the following command:
```bash
# base command example
scripts/create_model_fixture.sh <dev|test> <MODEL_NAME>

# create fixture for dev environment User model
scripts/create_model_fixture.sh dev User

# create fixture for test environment Profile model
scripts/create_model_fixture.sh test Profile
```

## Creating Fixtures For All Models

These commands will create fixtures for all models.
Prefer using the create_model_fixture.sh script to create a fixture for an individual model if possible.
Creating fixtures can only be done in dev or test environment.

To create fixtures for all models, run the following command:
```bash
# base command example
scripts/create_fixtures.sh <dev|test>

# create fixtures for dev environment
scripts/create_fixtures.sh dev

# create fixtures for test environment
scripts/create_fixtures.sh test
```


## Clear and Reload Database

These are commands to help clear and reload the DB with data for dev or test environment.

- The DB will first be cleared of all data.
- Then the fixtures for the given environment from either the fixtures/dev or fixtures/test folder will be loaded into the DB.
- This is for test or dev ENV only.

```bash
# base command example
scripts/load_db.sh <dev|test>

# clear and reload dev db
scripts/load_db.sh dev

# clear and reload test db
scripts/load_db.sh test
```


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