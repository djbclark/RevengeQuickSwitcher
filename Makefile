.PHONY: help build test clean install push

all: help

help:
	@echo "RevengeQuickSwitcher"
	@echo "  make install  - Install npm dependencies"
	@echo "  make build    - Compile plugin via esbuild"
	@echo "  make test     - Run unit tests"
	@echo "  make clean    - Remove build artifacts and node_modules"
	@echo "  make push     - Build, test, commit, and push to GitHub"

install:
	npm install

build:
	npm run build

test:
	npm test

clean:
	rm -rf dist/ node_modules/

push: test build
	@echo "Committing and pushing to GitHub..."
	git add .
	git commit -m "Auto-sync: $$(date +'%Y-%m-%d %H:%M:%S')" || echo "No new edits to commit."
	git push
