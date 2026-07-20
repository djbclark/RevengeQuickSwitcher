# RevengeQuickSwitcher — operator commands (run `just` or `just --list`).
# Tooling mirrors stayturgid (canonical): ruff, typos, markdownlint, prettier, pre-commit.

set shell := ["bash", "-uc"]

qss_device := env_var_or_default("QSS_DEVICE", "s24")
qss_guild := env_var_or_default("QSS_GUILD", "dcs")
stayturgid_repo := env_var_or_default("STAYTURGID_REPO", home_directory() / "ops/stayturgid")

# Show available recipes (default).
help:
    @just --list

# Install npm dependencies.
install:
    npm install

# Compile plugin via esbuild.
build:
    npm run build

# Run plugin unit tests (vitest).
test:
    npm test

# Type-check all src/ modules.
typecheck:
    npm run typecheck

# Typecheck + tests + build + manifest check.
verify:
    npm run verify

# v2 harness unit tests (device-free; scripts/qa).
qa-unit:
    cd scripts/qa && uv run --group dev pytest -q

# Ruff lint + format check (canonical Python lane).
ruff:
    ruff check .
    ruff format --check .

# Markdown lint.
markdownlint:
    markdownlint --config .markdownlint.json --ignore-path .markdownlintignore "**/*.md"

# Prettier format check (markdown).
prettier:
    prettier --check "*.md" "src/**/*.md" 2>/dev/null || prettier --check "*.md"

# Spell-check source.
typos:
    typos

# Biome lint + format check (TS/TSX/MJS).
biome:
    biome check .

# Offline link check across markdown docs.
lychee:
    lychee --offline --include-fragments "*.md"

# YAML lint (workflows, pre-commit config).
yamllint:
    yamllint -c .yamllint .github/ .pre-commit-config.yaml

# Shell lint.
shellcheck:
    shellcheck -S warning scripts/*.sh

# Shell format check.
shfmt:
    shfmt -d -i 2 -ci scripts/*.sh

# All linters (stayturgid convenience recipe).
check: ruff typos markdownlint prettier biome yamllint shellcheck shfmt lychee

# Broader lint suite: check + plugin verify + harness tests.
lint: check verify qa-unit

# Device QA harness (v1; Handsets + stayturgid).
qa:
    DEVICE_SCREEN_CONTROL_PROJECT=RevengeQuickSwitcher \
    STAYTURGID_SCREEN_PURPOSE=qss-qa \
    STAYTURGID_PRESENCE_QUIET=1 QSS_VLM=1 \
    python3 scripts/device_qa_qss.py {{ qss_device }} --guild {{ qss_guild }}

# Reachability + Discord package check only.
qa-dry:
    python3 scripts/device_qa_qss.py --dry-reach {{ qss_device }}

# Cross-project screen-control leases (DSCL v1).
lease-status:
    python3 {{ stayturgid_repo }}/control/bin/screen_lease.py status

# brew + download UI-TARS weights (~6GB).
vlm-install:
    bash scripts/vlm_install.sh

vlm-server:
    bash scripts/ui_tars_server.sh

vlm-check:
    python3 scripts/vlm_check.py

vlm-smoke:
    bash scripts/vlm_smoke.sh

vlm-stop:
    bash scripts/vlm_service.sh stop

vlm-service action:
    bash scripts/vlm_service.sh {{ action }}

# Remove node_modules/.
clean:
    rm -rf node_modules/

# Remove node_modules/ and dist/.
clean-all:
    rm -rf dist/ node_modules/
