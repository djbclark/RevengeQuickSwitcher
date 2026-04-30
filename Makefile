SOURCE_FILE = PROMPT_FOR_SECOND_OPINION.md
REPO_URL = git@github.com:djbclark/RevengeQuickSwitcher.git
.PHONY: help explode implode build clean distclean ship push pull init-repo
all: help

help:
	@echo "============================================================"
	@echo "RevengeQuickSwitcher (v3.9.7) - The AI Crowd-Source"
	@echo "============================================================"
	@echo "[AI COLLABORATION WORKFLOW]"
	@echo "  1. Download AI output and run it (make explode)."
	@echo "  2. Test and edit files locally in src/."
	@echo "  3. Run 'make push' to sync edits, bundle, and upload."
	@echo "  4. Upload 'PROMPT_FOR_SECOND_OPINION.md' back to AI."
	@echo "============================================================"
	@echo "[MANUAL COMMANDS]"
	@echo "  make explode    - Extract files and install NPM deps."
	@echo "  make build      - Compile and bundle plugin via esbuild."
	@echo "  make implode    - Sync local edits back to the Polyglot file."
	@echo "  make push       - Implodes, builds, and pushes to GitHub."
	@echo "  make pull       - Downloads updates and explodes them."
	@echo "  make clean      - Wipe node_modules and build artifacts."
	@echo "  make distclean  - (GNU Standard) Same as clean."
	@echo "============================================================"

# Development Pipeline
build:
	npm run build

explode:
	@python3 $(SOURCE_FILE) explode

implode:
	@python3 $(SOURCE_FILE) implode

ship: build implode

# Abstracted Git Workflow
init-repo:
	@echo "🌱 Initializing GitHub upload..."
	git init
	git branch -M main
	git add .
	git commit -m "Initial commit" || true
	git remote add origin $(REPO_URL) || echo "Remote already exists."
	@echo "🚀 Force-pushing to establish local as source of truth..."
	git push -u origin main -f
	@echo "✅ Project initialized and uploaded."

push: ship
	@echo "🚀 Committing and uploading to GitHub..."
	git add .
	git commit -m "Auto-sync: $$(date +'%Y-%m-%d %H:%M:%S')" || echo "No new edits to commit."
	git push
	@echo "✅ Upload complete! You can now hand $(SOURCE_FILE) back to the AI."

pull:
	@echo "⬇️ Downloading from GitHub..."
	git pull
	@echo "💥 Exploding new changes..."
	@$(MAKE) explode

clean:
	rm -rf dist/ node_modules/ package-lock.json

distclean: clean
