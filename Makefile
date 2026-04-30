SOURCE_FILE = PROMPT_FOR_SECOND_OPINION.md
REPO_URL = git@github.com:djbclark/RevengeQuickSwitcher.git
.PHONY: help explode implode build test clean ship push pull init-repo
all: help

help:
	@echo "============================================================"
	@echo "RevengeQuickSwitcher (v3.9.0) - The Git Abstraction"
	@echo "============================================================"
	@echo "[DEVELOPMENT]"
	@echo "  make explode    - Bootstrap (Extract files, install deps)."
	@echo "  make build      - Run tests, then bundle via esbuild."
	@echo ""
	@echo "[VERSION CONTROL (No Git Knowledge Required)]"
	@echo "  make init-repo  - (ONE-TIME) Link local folder to GitHub & upload."
	@echo "  make push       - (SAFE) Implodes, tests, builds, and uploads changes."
	@echo "  make pull       - Downloads updates from GitHub and explodes them."
	@echo ""
	@echo "[MAINTENANCE]"
	@echo "  make implode    - Sync local edits back to the Polyglot file."
	@echo "  make clean      - Wipe node_modules and build artifacts."
	@echo "============================================================"

# Development Pipeline
test:
	npm run test

build: test
	npm run build

explode:
	@python3 $(SOURCE_FILE) explode

implode:
	@python3 $(SOURCE_FILE) implode

ship: test build implode

# Abstracted Git Workflow
init-repo:
	@echo "🌱 Initializing GitHub upload..."
	git init
	git branch -M main
	git add .
	git commit -m "Initial commit" || true
	git remote add origin $(REPO_URL) || echo "Remote already exists."
	git push -u origin main
	@echo "✅ Project initialized and uploaded."

push: ship
	@echo "🚀 Committing and uploading to GitHub..."
	git add .
	git commit -m "Auto-sync: $$(date +'%Y-%m-%d %H:%M:%S')" || echo "No new edits to commit."
	git push
	@echo "✅ Upload complete."

pull:
	@echo "⬇️ Downloading from GitHub..."
	git pull
	@echo "💥 Exploding new changes..."
	@$(MAKE) explode

clean:
	rm -rf dist/ node_modules/ coverage/ package-lock.json
