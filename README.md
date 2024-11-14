# OnlyPaws API

### Running Tests

```bash
docker-compose run --rm only-paws-app sh -c "python manage.py test apps"
```

### Run tests with coverage
```bash
docker-compose run --rm only-paws-app sh -c "coverage run manage.py test apps"
```


### Generating cli coverage report

```bash
docker-compose run --rm only-paws-app sh -c "coverage report -m"
```

### Generating html coverage report

```bash
docker-compose run --rm only-paws-app sh -c "coverage html"
```


## Commits

### Commit Message Types
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

### Creating Fixture for Individual Model

docker-compose run --rm only-paws-app sh -c "python manage.py dumpdata --format json --indent 4 --output fixtures/<MODEL_NAME>.json core_app.<MODEL_NAME>"

### Creating Fixtures

```bash
python manage.py create_fixtures
```

### Clear and reload DB

This is for test ENV only

```bash
python manage.py clear_and_load_db
```