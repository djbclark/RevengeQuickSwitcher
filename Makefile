.PHONY: help build test typecheck verify clean clean-all install qa qa-dry \
	vlm-install vlm-server vlm-check vlm-stop vlm-smoke \
	vlm-service-install vlm-service-uninstall vlm-service-start vlm-service-stop vlm-service-restart vlm-service-status

all: help

help:
	@echo "RevengeQuickSwitcher"
	@echo "  make install    - Install npm dependencies"
	@echo "  make build      - Compile plugin via esbuild"
	@echo "  make test       - Run unit tests"
	@echo "  make typecheck  - Type-check all src/ modules"
	@echo "  make verify     - Run typecheck, tests, build, and manifest check"
	@echo "  make qa         - Device QA harness (Handsets + stayturgid; QSS_DEVICE=p7a)"
	@echo "  make qa-dry     - Reachability + Discord package check only"
	@echo "  make vlm-install - brew + download UI-TARS weights (~6GB) to ~/.local/share/ui-tars/"
	@echo "  make vlm-check   - Smoke-test VLM server health"
	@echo "  (UI-TARS start/stop: launchctl — see PATHS.md; make vlm-service-* are thin wrappers)"
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

QSS_DEVICE ?= p7a
QSS_GUILD ?= dcs

verify:
	npm run verify

qa:
	STAYTURGID_PRESENCE_QUIET=1 QSS_VLM=1 python3 scripts/device_qa_qss.py $(QSS_DEVICE) --guild $(QSS_GUILD)

qa-dry:
	python3 scripts/device_qa_qss.py --dry-reach $(QSS_DEVICE)

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

vlm-service-install:
	bash scripts/vlm_service.sh install

vlm-service-uninstall:
	bash scripts/vlm_service.sh uninstall

vlm-service-start:
	bash scripts/vlm_service.sh start

vlm-service-stop:
	bash scripts/vlm_service.sh stop

vlm-service-restart:
	bash scripts/vlm_service.sh restart

vlm-service-status:
	bash scripts/vlm_service.sh status

clean:
	rm -rf node_modules/

clean-all:
	rm -rf dist/ node_modules/
