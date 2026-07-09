.PHONY: help build test typecheck verify clean clean-all install

all: help

help:
	@echo "RevengeQuickSwitcher"
	@echo "  make install    - Install npm dependencies"
	@echo "  make build      - Compile plugin via esbuild"
	@echo "  make test       - Run unit tests"
	@echo "  make typecheck  - Type-check all src/ modules"
	@echo "  make verify     - Run typecheck, tests, build, and manifest check"
	@echo "  make clean      - Remove node_modules/"
	@echo "  make clean-all  - Remove node_modules/ and dist/"

install:
	npm install

build:
	npm run build

test:
	npm test

typecheck:
	npm run typecheck

verify:
	npm run verify

clean:
	rm -rf node_modules/

clean-all:
	rm -rf dist/ node_modules/
