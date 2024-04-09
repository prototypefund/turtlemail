DIR_BUILD ?= build
DIR_SRC = src

NODE_MODULES = node_modules
NODE ?= node
NPM ?= npm
NPX ?= npx
ESLINT ?= $(NODE_MODULES)/.bin/eslint
DOCKER ?= $(shell command -v docker)
COMPOSE ?= $(shell command -v docker-compose || echo "$(DOCKER) compose")

OUTPUT_DIR ?= turtlemail/static/turtlemail/bundled/
OUTPUT_ASSET_MANIFEST = $(OUTPUT_DIR)/.vite/manifest.json

DEPS_ASSETS = $(shell find "$(DIR_SRC)" -type f)

define help_message =
dev:          start dev environment
migrate:      migrate database (in dev environment)
build:        build app dependencies
update-translations: Update .po files
endef

.PHONY: help
help:
	@$(info $(help_message)):

.PHONY: build
build: assets

$(NODE_MODULES): package.json package-lock.json
	ADBLOCK=true "$(NPM)" ci --no-progress
	"$(NPX)" --yes -- update-browserslist-db@latest
	@touch --no-create "$(NODE_MODULES)"

$(ESLINT): $(NODE_MODULES)

$(OUTPUT_ASSET_MANIFEST): $(NODE_MODULES) $(DEPS_ASSETS)
	"$(NPM)" run build

.PHONY: clean
clean:
	rm -rf \
			.tox \
			.coverage \
			"$(NODE_MODULES)" \
			"$(OUTPUT_DIR)"

.PHONY: assets
assets: $(OUTPUT_ASSET_MANIFEST)

.PHONY: dev
dev:
	COMPOSE_FILE=docker-compose.yml:docker-compose.dev.yml $(COMPOSE) up --build --force-recreate

.PHONY: migrate
migrate:
	$(COMPOSE) exec -it backend turtlemailctl migrate

.PHONY: update-translations
update-translations:
	poetry run pybabel extract -F babel.cfg -o turtlemail/locale/django.pot .
	poetry run pybabel update -i turtlemail/locale/django.pot --domain django --output-dir turtlemail/locale
	rm turtlemail/locale/django.pot

.PHONY: fixtures
fixtures:
	$(COMPOSE) exec -it backend turtlemailctl initdata
