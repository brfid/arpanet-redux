.DEFAULT_GOAL := help

REPOSITORY_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
GIT_COMMON_DIR := $(shell git -C "$(REPOSITORY_ROOT)" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
PRIMARY_CHECKOUT_ROOT := $(if $(GIT_COMMON_DIR),$(abspath $(GIT_COMMON_DIR)/..),$(REPOSITORY_ROOT))
LAB_ROOT ?= $(abspath $(PRIMARY_CHECKOUT_ROOT)/../arpanet-redux-lab)
BOOTSTRAP_PYTHON ?= python3
LAB_PYTHON ?= $(LAB_ROOT)/.venv/bin/python3
PYTHON ?= $(if $(wildcard $(LAB_PYTHON)),$(LAB_PYTHON),python3)
ARPANET_ROOT ?= $(LAB_ROOT)/work/arpanet
LINUX_NCP_ROOT ?= $(ARPANET_ROOT)/src/linux-ncp
ITS_ROOT ?= $(LAB_ROOT)/work/its-readdress-src
NETWORK_UNIX_ROOT ?= $(LAB_ROOT)/work/network-unix-v6
IMP11A_ROOT ?= $(LAB_ROOT)/work/open-simh
H316_ROOT ?= $(LINUX_NCP_ROOT)/test/simh
KA10_ROOT ?= $(LAB_ROOT)/work/ka10-simh
H316_BIN ?= $(H316_ROOT)/BIN/h316
PDP10_KA_BIN ?= $(KA10_ROOT)/BIN/pdp10-ka
PDP11_BIN ?= $(IMP11A_ROOT)/BIN/pdp11
RESULTS_ROOT ?= $(LAB_ROOT)/results
NCP_BUILD_RECEIPT ?= $(LINUX_NCP_ROOT)/.brfid-build-receipt.json
ITS_BUILD_RECEIPT ?= $(ITS_ROOT)/.brfid-build-receipt.json
ifndef RUN_ID
RUN_ID := $(shell python3 -c 'import datetime, uuid; print(datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + str(uuid.uuid4()))')
endif
PDP11_BASE_IMAGE_DIR := $(shell "$(BOOTSTRAP_PYTHON)" -c 'import sys; sys.path.insert(0, sys.argv[1]); from pathlib import Path; from pdp11_base import default_image_dir; print(default_image_dir(Path(sys.argv[2])))' "$(REPOSITORY_ROOT)/scripts" "$(LAB_ROOT)")
PDP11_BASE_ROOT ?= $(PDP11_BASE_IMAGE_DIR)/ncp_root.rl01
PDP11_BASE_SWAP ?= $(PDP11_BASE_IMAGE_DIR)/ncp_swap.rl01
PDP11_BUILD_ROOT ?= $(RESULTS_ROOT)/pdp11-telnet-build-$(RUN_ID)
PDP11_BUILD_RECEIPT ?= $(PDP11_BUILD_ROOT)/pdp11-build-receipt.json
PDP11_SELECTED_BUILD_ROOT := $(shell "$(PYTHON)" "$(REPOSITORY_ROOT)/scripts/lab-state.py" resolve "$(LAB_ROOT)" pdp11-build --results-root "$(RESULTS_ROOT)" 2>/dev/null)
PDP11_RETAINED_BUILD_ROOT ?= $(if $(filter file,$(origin PDP11_BUILD_ROOT)),$(if $(PDP11_SELECTED_BUILD_ROOT),$(PDP11_SELECTED_BUILD_ROOT),$(PDP11_BUILD_ROOT)),$(PDP11_BUILD_ROOT))
PDP11_DOCTOR_BUILD_ARGUMENT = $(if $(filter file,$(origin PDP11_BUILD_ROOT)),,--pdp11-build-root "$(PDP11_BUILD_ROOT)")
PDP11_INTERACTIVE_BUILD_ROOT ?= $(PDP11_RETAINED_BUILD_ROOT)
NCC_PDP11_BUILD_ROOT ?= $(PDP11_RETAINED_BUILD_ROOT)
PDP11_BASE_SOURCE_ROOT ?=
PDP11_BASE_SOURCE_SWAP ?=
NCC_ALTERNATE_DURATION ?= 130
NCC_LOOPBACK_DURATION ?= 130
NCC_PDP11_ITS_DURATION ?= 150
NCC_PDP11_ITS_FAILOVER_DURATION ?= 300
NCC_APPLICATION_RELAY_DURATION ?= 420
TELNET_FAILOVER_RELAY_DURATION ?= 3600
NCC_DIRECT_FORWARD_SECONDS ?= 45
NCC_LAB_ROOT ?= $(LAB_ROOT)
NCC_SELECTED_RESULT := $(shell "$(PYTHON)" "$(REPOSITORY_ROOT)/scripts/lab-state.py" resolve "$(NCC_LAB_ROOT)" ncc-coexistence --results-root "$(RESULTS_ROOT)" 2>/dev/null)
NCC_SELECTED_FAILOVER_RESULT := $(shell "$(PYTHON)" "$(REPOSITORY_ROOT)/scripts/lab-state.py" resolve "$(NCC_LAB_ROOT)" ncc-failover --results-root "$(RESULTS_ROOT)" 2>/dev/null)
NCC_RESULT ?= $(NCC_SELECTED_RESULT)
NCC_FAILOVER_RESULT ?= $(NCC_SELECTED_FAILOVER_RESULT)
NCC_VIEW_PORT ?= 8767
NCC_WATCH_PORT ?= 8765
TELNET_COMMAND_TIMEOUT ?= 60
TELNET_MAX_COMMAND_BYTES ?= 256
TELNET_MAX_COMMANDS ?= 100
TELNET_MAX_RESPONSE_BYTES ?= 1048576
TELNET_MAX_INPUT_BYTES ?= 1048576
TELNET_MAX_OUTPUT_BYTES ?= 8388608
TELNET_MAX_CHUNK_BYTES ?= 4096
TELNET_PREFLIGHT_VERBOSE ?= 0
RESULT ?=
TELNET_PREFLIGHT_REDIRECT = $(if $(filter 1,$(TELNET_PREFLIGHT_VERBOSE)),,>/dev/null)

.NOTPARALLEL:

.PHONY: help lab-setup lab-setup-plan doctor prune-media install-pdp11-base select-pdp11-build select-ncc-result select-ncc-failover-result check-source-only check-source-history test test-simh-env verify-assets verify-sources verify-binaries verify-ncp-source verify-pdp11-source build-ncp build-its build-pdp11-telnet verify verify-router verify-mixed verify-two-its verify-pdp11-its verify-ncc-alternate-path verify-ncc-line-loopback verify-ncc-pdp11-its verify-ncc-pdp11-its-failover smoke-router smoke-mixed smoke-two-its smoke-pdp11-its smoke-ncc-alternate-path smoke-ncc-line-loopback smoke-ncc-pdp11-its smoke-ncc-pdp11-its-failover telnet telnet-failover telnet-check ncc ncc-failover run-ncc watch-ncc view-ncc view-ncc-failover

help:
	@printf 'ARPANET Redux\n\n'
	@printf 'First clone / diagnose:\n'
	@printf '  make test              source-only checks (no external downloads)\n'
	@printf '  make lab-setup         fetch pinned runtime sources and build host tools\n'
	@printf '  make doctor            report readiness and exact next actions\n\n'
	@printf '  make diagnose-run RESULT=/path/to/result  explain a retained run\n\n'
	@printf 'Prepare historical media:\n'
	@printf '  make build-pdp11-base  fetch pinned archives and reconstruct base disks\n'
	@printf '  make install-pdp11-base PDP11_BASE_SOURCE_ROOT=/path/root.rl01 PDP11_BASE_SOURCE_SWAP=/path/swap.rl01\n'
	@printf '  make build-pdp11-telnet build and select receipt-bound guest media\n\n'
	@printf 'Laboratory maintenance:\n'
	@printf '  make prune-media       preview removable staged media (never deletes)\n\n'
	@printf 'Start:\n'
	@printf '  make telnet            foreground historical Network UNIX terminal\n'
	@printf '  make telnet-failover   foreground terminal with a controller-owned link cut\n'
	@printf '  make ncc               live passive NCC operator console\n'
	@printf '  make ncc-failover      live console with application-link failover\n\n'
	@printf 'Replay:\n'
	@printf '  make view-ncc          newest selected passing coexistence result\n'
	@printf '  make view-ncc-failover newest selected passing failover result\n\n'
	@printf 'See docs/getting-started.md; override LAB_ROOT=/absolute/path when needed.\n'

lab-setup:
	$(BOOTSTRAP_PYTHON) ./scripts/lab-setup.py "$(LAB_ROOT)"

lab-setup-plan:
	$(BOOTSTRAP_PYTHON) ./scripts/lab-setup.py "$(LAB_ROOT)" --plan

.PHONY: build-pdp11-base build-pdp11-base-plan
build-pdp11-base:
	$(BOOTSTRAP_PYTHON) ./scripts/pdp11_base.py build "$(LAB_ROOT)" --network-unix-root "$(NETWORK_UNIX_ROOT)"

build-pdp11-base-plan:
	$(BOOTSTRAP_PYTHON) ./scripts/pdp11_base.py build "$(LAB_ROOT)" --network-unix-root "$(NETWORK_UNIX_ROOT)" --plan

doctor:
	$(PYTHON) ./scripts/lab-doctor.py "$(LAB_ROOT)" --python "$(PYTHON)" --arpanet-root "$(ARPANET_ROOT)" --linux-ncp-root "$(LINUX_NCP_ROOT)" --h316-root "$(H316_ROOT)" --ka10-root "$(KA10_ROOT)" --imp11a-root "$(IMP11A_ROOT)" --network-unix-root "$(NETWORK_UNIX_ROOT)" --h316 "$(H316_BIN)" --pdp10-ka "$(PDP10_KA_BIN)" --pdp11 "$(PDP11_BIN)" --base-root "$(PDP11_BASE_ROOT)" --base-swap "$(PDP11_BASE_SWAP)" --results-root "$(RESULTS_ROOT)" $(PDP11_DOCTOR_BUILD_ARGUMENT)

.PHONY: diagnose-run
diagnose-run: export ARPANET_DIAGNOSTIC_RESULT = $(value RESULT)
diagnose-run:
	@test -n "$$ARPANET_DIAGNOSTIC_RESULT" || { printf '%s\n' 'Set RESULT=/absolute/path/to/a/smoke-or-terminal-result.' >&2; exit 64; }
	$(BOOTSTRAP_PYTHON) ./scripts/diagnose-run.py -- "$$ARPANET_DIAGNOSTIC_RESULT"

prune-media:
	$(BOOTSTRAP_PYTHON) ./scripts/prune-media.py "$(LAB_ROOT)" --results-root "$(RESULTS_ROOT)"

install-pdp11-base:
	@test -n "$(PDP11_BASE_SOURCE_ROOT)" -a -n "$(PDP11_BASE_SOURCE_SWAP)" || { printf '%s\n' 'Set PDP11_BASE_SOURCE_ROOT and PDP11_BASE_SOURCE_SWAP to your user-supplied images.' >&2; exit 64; }
	$(BOOTSTRAP_PYTHON) ./scripts/install-pdp11-base.py "$(LAB_ROOT)" "$(PDP11_BASE_SOURCE_ROOT)" "$(PDP11_BASE_SOURCE_SWAP)"

select-pdp11-build:
	$(PYTHON) ./scripts/lab-state.py select "$(LAB_ROOT)" pdp11-build "$(PDP11_BUILD_ROOT)"

select-ncc-result:
	$(PYTHON) ./scripts/lab-state.py select "$(NCC_LAB_ROOT)" ncc-coexistence "$(NCC_RESULT)"

select-ncc-failover-result:
	$(PYTHON) ./scripts/lab-state.py select "$(NCC_LAB_ROOT)" ncc-failover "$(NCC_FAILOVER_RESULT)"

check-source-only:
	./scripts/check-source-only.py

check-source-history:
	./scripts/check-source-only.py --history HEAD

test: check-source-only
	python3 -m unittest discover -s tests -v
	./tests/test_runtime.sh

test-simh-env:
	./tests/test-simh-env.sh "$(H316_BIN)" "$(PDP10_KA_BIN)"

verify-assets:
	./scripts/verify-assets.sh all "$(ARPANET_ROOT)"

verify-sources:
	./scripts/verify-sources.py "$(LAB_ROOT)"

verify-binaries:
	./scripts/verify-simulator-binaries.py --h316 "$(H316_BIN)" --pdp10-ka "$(PDP10_KA_BIN)"

verify-ncp-source:
	./scripts/verify-sources.py "$(LAB_ROOT)" --name linux-ncp

build-ncp: verify-ncp-source
	./scripts/build-ncp.sh "$(LINUX_NCP_ROOT)" "$(NCP_BUILD_RECEIPT)"

build-its:
	./scripts/verify-sources.py "$(LAB_ROOT)" --name pdp10-its
	./scripts/build-its.sh "$(ITS_ROOT)" "$(ITS_BUILD_RECEIPT)"

verify-pdp11-source:
	./scripts/verify-sources.py "$(LAB_ROOT)" --name network-unix-v6 --name imp11a-simh
	./scripts/verify-simulator-binaries.py --pdp11 "$(PDP11_BIN)"

build-pdp11-telnet: verify-pdp11-source
	PYTHON="$(PYTHON)" ./scripts/build-pdp11-telnet.sh "$(NETWORK_UNIX_ROOT)" "$(IMP11A_ROOT)" "$(PDP11_BIN)" "$(PDP11_BASE_ROOT)" "$(PDP11_BASE_SWAP)" "$(PDP11_BUILD_ROOT)"
	$(PYTHON) ./scripts/lab-state.py select "$(LAB_ROOT)" pdp11-build "$(PDP11_BUILD_ROOT)"

verify: build-ncp
	./scripts/verify-sources.py "$(LAB_ROOT)"
	./scripts/verify-assets.sh all "$(ARPANET_ROOT)"
	./scripts/verify-simulator-binaries.py --h316 "$(H316_BIN)" --pdp10-ka "$(PDP10_KA_BIN)"

verify-router: build-ncp
	./scripts/verify-sources.py "$(LAB_ROOT)" --name h316-simh
	./scripts/verify-assets.sh router "$(ARPANET_ROOT)"
	./scripts/verify-simulator-binaries.py --h316 "$(H316_BIN)"

verify-mixed: build-ncp
	./scripts/verify-sources.py "$(LAB_ROOT)" --name arpanet-in-a-box --name h316-simh --name ka10-simh
	./scripts/verify-assets.sh mixed "$(ARPANET_ROOT)"
	./scripts/verify-simulator-binaries.py --h316 "$(H316_BIN)" --pdp10-ka "$(PDP10_KA_BIN)"

verify-two-its:
	./scripts/verify-sources.py "$(LAB_ROOT)" --name arpanet-in-a-box --name h316-simh --name ka10-simh --name pdp10-its
	./scripts/verify-assets.sh mixed "$(ARPANET_ROOT)"
	./scripts/verify-simulator-binaries.py --h316 "$(H316_BIN)" --pdp10-ka "$(PDP10_KA_BIN)"
	./scripts/its-build-receipt.py verify "$(ITS_ROOT)" "$(ITS_BUILD_RECEIPT)"

verify-pdp11-its:
	./scripts/verify-sources.py "$(LAB_ROOT)" --name arpanet-in-a-box --name h316-simh --name ka10-simh --name imp11a-simh --name network-unix-v6
	./scripts/verify-assets.sh mixed "$(ARPANET_ROOT)"
	./scripts/verify-simulator-binaries.py --h316 "$(H316_BIN)" --pdp10-ka "$(PDP10_KA_BIN)" --pdp11 "$(PDP11_BIN)"
	./scripts/pdp11-build-receipt.py verify "$(PDP11_BUILD_RECEIPT)"

verify-ncc-alternate-path:
	./scripts/verify-sources.py "$(LAB_ROOT)" --name arpanet-in-a-box --name h316-simh
	./scripts/verify-assets.sh mixed "$(ARPANET_ROOT)"
	./scripts/verify-simulator-binaries.py --h316 "$(H316_BIN)"

verify-ncc-line-loopback: verify-ncc-alternate-path

verify-ncc-pdp11-its: verify-pdp11-its

verify-ncc-pdp11-its-failover: verify-pdp11-its

smoke-router: verify-router
	./scripts/smoke-router-oracle.sh "$(LINUX_NCP_ROOT)" "$(H316_BIN)" "$(NCP_BUILD_RECEIPT)" "$(RESULTS_ROOT)/router-oracle-$(RUN_ID)"

smoke-mixed: verify-mixed
	./scripts/smoke-its-linux.sh "$(ARPANET_ROOT)" "$(LINUX_NCP_ROOT)" "$(H316_BIN)" "$(PDP10_KA_BIN)" "$(NCP_BUILD_RECEIPT)" "$(RESULTS_ROOT)/its-linux-$(RUN_ID)"

smoke-two-its: verify-two-its
	./scripts/smoke-two-its.sh "$(ARPANET_ROOT)" "$(ITS_ROOT)" "$(H316_BIN)" "$(PDP10_KA_BIN)" "$(ITS_BUILD_RECEIPT)" "$(RESULTS_ROOT)/two-its-telnet-$(RUN_ID)"

smoke-pdp11-its: verify-pdp11-its
	./scripts/smoke-pdp11-its.sh "$(ARPANET_ROOT)" "$(NETWORK_UNIX_ROOT)" "$(IMP11A_ROOT)" "$(H316_BIN)" "$(PDP10_KA_BIN)" "$(PDP11_BIN)" "$(PDP11_BUILD_ROOT)" "$(RESULTS_ROOT)/pdp11-its-telnet-$(RUN_ID)"

smoke-ncc-alternate-path: verify-ncc-alternate-path
	BRFID_NCC_RECEIVER_DURATION="$(NCC_ALTERNATE_DURATION)" BRFID_DIRECT_FORWARD_SECONDS="$(NCC_DIRECT_FORWARD_SECONDS)" PYTHON="$(PYTHON)" ./scripts/smoke-ncc-alternate-path.sh "$(ARPANET_ROOT)" "$(H316_BIN)" "$(RESULTS_ROOT)/ncc-alternate-path-fault-$(RUN_ID)"

smoke-ncc-line-loopback: verify-ncc-line-loopback
	BRFID_NCC_RECEIVER_DURATION="$(NCC_LOOPBACK_DURATION)" BRFID_DIRECT_FORWARD_SECONDS="$(NCC_DIRECT_FORWARD_SECONDS)" PYTHON="$(PYTHON)" ./scripts/smoke-ncc-line-loopback.sh "$(ARPANET_ROOT)" "$(H316_BIN)" "$(RESULTS_ROOT)/ncc-line-loopback-$(RUN_ID)"

smoke-ncc-pdp11-its: verify-ncc-pdp11-its
	BRFID_NCC_RECEIVER_DURATION="$(NCC_PDP11_ITS_DURATION)" PYTHON="$(PYTHON)" ./scripts/smoke-ncc-pdp11-its.sh "$(ARPANET_ROOT)" "$(NETWORK_UNIX_ROOT)" "$(IMP11A_ROOT)" "$(H316_BIN)" "$(PDP10_KA_BIN)" "$(PDP11_BIN)" "$(PDP11_BUILD_ROOT)" "$(RESULTS_ROOT)/ncc-pdp11-its-coexistence-$(RUN_ID)"

smoke-ncc-pdp11-its-failover: verify-ncc-pdp11-its-failover
	BRFID_NCC_RECEIVER_DURATION="$(NCC_PDP11_ITS_FAILOVER_DURATION)" BRFID_APPLICATION_RELAY_DURATION="$(NCC_APPLICATION_RELAY_DURATION)" PYTHON="$(PYTHON)" ./scripts/smoke-ncc-pdp11-its-failover.sh "$(ARPANET_ROOT)" "$(NETWORK_UNIX_ROOT)" "$(IMP11A_ROOT)" "$(H316_BIN)" "$(PDP10_KA_BIN)" "$(PDP11_BIN)" "$(PDP11_BUILD_ROOT)" "$(RESULTS_ROOT)/ncc-pdp11-its-application-failover-$(RUN_ID)"

telnet:
	@printf '\nARPANET REDUX // HISTORICAL NETWORK TERMINAL\n'
	@printf '  [PDP-11] Network UNIX 176\n'
	@printf '       |\n'
	@printf '  [H316] IMP 62 ========= [H316] IMP 6\n'
	@printf '                                  |\n'
	@printf '                             [KA10] ITS 106 / TELSER\n\n'
	@printf '  [preflight] verifying pinned sources, media, and simulators ...\n'
	@$(MAKE) -s --no-print-directory PDP11_BUILD_ROOT="$(PDP11_INTERACTIVE_BUILD_ROOT)" verify-pdp11-its $(TELNET_PREFLIGHT_REDIRECT) || { status=$$?; printf '\n  [preflight] not ready; running the laboratory doctor ...\n\n' >&2; $(MAKE) -s --no-print-directory PDP11_BUILD_ROOT="$(PDP11_INTERACTIVE_BUILD_ROOT)" doctor || true; exit $$status; }
	@printf '  [preflight] ready; detailed simulator output will stay in the retained result\n\n'
	@BRFID_TELNET_MODE=terminal BRFID_TELNET_MAX_INPUT_BYTES="$(TELNET_MAX_INPUT_BYTES)" BRFID_TELNET_MAX_OUTPUT_BYTES="$(TELNET_MAX_OUTPUT_BYTES)" BRFID_TELNET_MAX_CHUNK_BYTES="$(TELNET_MAX_CHUNK_BYTES)" ./scripts/telnet-pdp11-its.sh "$(ARPANET_ROOT)" "$(NETWORK_UNIX_ROOT)" "$(IMP11A_ROOT)" "$(H316_BIN)" "$(PDP10_KA_BIN)" "$(PDP11_BIN)" "$(PDP11_INTERACTIVE_BUILD_ROOT)" "$(RESULTS_ROOT)/pdp11-its-terminal-$(RUN_ID)"

telnet-failover:
	@printf '\nARPANET REDUX // INTERACTIVE NETWORK FAILOVER\n'
	@printf '  [PDP-11] Network UNIX 176\n'
	@printf '       |\n'
	@printf '  [H316] IMP 62 === cut === [H316] IMP 6\n'
	@printf '          \\                 /       |\n'
	@printf '           +--- [H316] IMP 7 --+  [KA10] ITS 106 / TELSER\n\n'
	@printf '  [preflight] verifying the accepted failover topology and pinned inputs ...\n'
	@$(MAKE) -s --no-print-directory PDP11_BUILD_ROOT="$(PDP11_INTERACTIVE_BUILD_ROOT)" verify-ncc-pdp11-its-failover $(TELNET_PREFLIGHT_REDIRECT) || { status=$$?; printf '\n  [preflight] not ready; running the laboratory doctor ...\n\n' >&2; $(MAKE) -s --no-print-directory PDP11_BUILD_ROOT="$(PDP11_INTERACTIVE_BUILD_ROOT)" doctor || true; exit $$status; }
	@printf '  [preflight] ready; detailed simulator output will stay in the retained result\n\n'
	@BRFID_FAILOVER_MODE=terminal BRFID_APPLICATION_RELAY_DURATION="$(TELNET_FAILOVER_RELAY_DURATION)" BRFID_TELNET_MAX_INPUT_BYTES="$(TELNET_MAX_INPUT_BYTES)" BRFID_TELNET_MAX_OUTPUT_BYTES="$(TELNET_MAX_OUTPUT_BYTES)" BRFID_TELNET_MAX_CHUNK_BYTES="$(TELNET_MAX_CHUNK_BYTES)" PYTHON="$(PYTHON)" ./scripts/smoke-ncc-pdp11-its-failover.sh "$(ARPANET_ROOT)" "$(NETWORK_UNIX_ROOT)" "$(IMP11A_ROOT)" "$(H316_BIN)" "$(PDP10_KA_BIN)" "$(PDP11_BIN)" "$(PDP11_INTERACTIVE_BUILD_ROOT)" "$(RESULTS_ROOT)/pdp11-its-interactive-failover-$(RUN_ID)"

telnet-check:
	@printf '\nARPANET REDUX // PROMPT-FRAMED TELNET CHECK\n'
	@printf '  [PDP-11] Network UNIX 176\n'
	@printf '       |\n'
	@printf '  [H316] IMP 62 ========= [H316] IMP 6\n'
	@printf '                                  |\n'
	@printf '                             [KA10] ITS 106 / TELSER\n\n'
	@printf '  [preflight] verifying pinned sources, media, and simulators ...\n'
	@$(MAKE) -s --no-print-directory PDP11_BUILD_ROOT="$(PDP11_INTERACTIVE_BUILD_ROOT)" verify-pdp11-its $(TELNET_PREFLIGHT_REDIRECT) || { status=$$?; printf '\n  [preflight] not ready; running the laboratory doctor ...\n\n' >&2; $(MAKE) -s --no-print-directory PDP11_BUILD_ROOT="$(PDP11_INTERACTIVE_BUILD_ROOT)" doctor || true; exit $$status; }
	@printf '  [preflight] ready; detailed simulator output will stay in the retained result\n\n'
	@BRFID_TELNET_MODE=line BRFID_TELNET_COMMAND_TIMEOUT="$(TELNET_COMMAND_TIMEOUT)" BRFID_TELNET_MAX_COMMAND_BYTES="$(TELNET_MAX_COMMAND_BYTES)" BRFID_TELNET_MAX_COMMANDS="$(TELNET_MAX_COMMANDS)" BRFID_TELNET_MAX_RESPONSE_BYTES="$(TELNET_MAX_RESPONSE_BYTES)" ./scripts/telnet-pdp11-its.sh "$(ARPANET_ROOT)" "$(NETWORK_UNIX_ROOT)" "$(IMP11A_ROOT)" "$(H316_BIN)" "$(PDP10_KA_BIN)" "$(PDP11_BIN)" "$(PDP11_INTERACTIVE_BUILD_ROOT)" "$(RESULTS_ROOT)/pdp11-its-interactive-$(RUN_ID)"

run-ncc: smoke-ncc-pdp11-its
	@$(PYTHON) ./scripts/lab-state.py select "$(NCC_LAB_ROOT)" ncc-coexistence "$(RESULTS_ROOT)/ncc-pdp11-its-coexistence-$(RUN_ID)"
	@echo "Completed NCC result: $(RESULTS_ROOT)/ncc-pdp11-its-coexistence-$(RUN_ID)"

ncc:
	@$(MAKE) -s --no-print-directory PDP11_BUILD_ROOT="$(NCC_PDP11_BUILD_ROOT)" verify-ncc-pdp11-its || { status=$$?; printf '\nNCC preflight is not ready; running the laboratory doctor ...\n\n' >&2; $(MAKE) -s --no-print-directory PDP11_BUILD_ROOT="$(NCC_PDP11_BUILD_ROOT)" doctor || true; exit $$status; }
	BRFID_NCC_RECEIVER_DURATION="$(NCC_PDP11_ITS_DURATION)" $(PYTHON) ./scripts/ncc-operate-pdp11-its.py --arpanet-root "$(ARPANET_ROOT)" --network-unix-root "$(NETWORK_UNIX_ROOT)" --imp11a-root "$(IMP11A_ROOT)" --h316 "$(H316_BIN)" --pdp10-ka "$(PDP10_KA_BIN)" --pdp11 "$(PDP11_BIN)" --pdp11-build-root "$(NCC_PDP11_BUILD_ROOT)" --results-root "$(RESULTS_ROOT)" --run-id "$(RUN_ID)" --topology config/topologies/ncc-pdp11-its-coexistence.json --port "$(NCC_WATCH_PORT)"
	@$(PYTHON) ./scripts/lab-state.py select "$(NCC_LAB_ROOT)" ncc-coexistence "$(RESULTS_ROOT)/ncc-pdp11-its-coexistence-$(RUN_ID)"

ncc-failover:
	@$(MAKE) -s --no-print-directory PDP11_BUILD_ROOT="$(NCC_PDP11_BUILD_ROOT)" verify-ncc-pdp11-its-failover || { status=$$?; printf '\nNCC preflight is not ready; running the laboratory doctor ...\n\n' >&2; $(MAKE) -s --no-print-directory PDP11_BUILD_ROOT="$(NCC_PDP11_BUILD_ROOT)" doctor || true; exit $$status; }
	BRFID_NCC_RECEIVER_DURATION="$(NCC_PDP11_ITS_FAILOVER_DURATION)" BRFID_APPLICATION_RELAY_DURATION="$(NCC_APPLICATION_RELAY_DURATION)" $(PYTHON) ./scripts/ncc-operate-pdp11-its.py --scenario failover --arpanet-root "$(ARPANET_ROOT)" --network-unix-root "$(NETWORK_UNIX_ROOT)" --imp11a-root "$(IMP11A_ROOT)" --h316 "$(H316_BIN)" --pdp10-ka "$(PDP10_KA_BIN)" --pdp11 "$(PDP11_BIN)" --pdp11-build-root "$(NCC_PDP11_BUILD_ROOT)" --results-root "$(RESULTS_ROOT)" --run-id "$(RUN_ID)" --topology config/topologies/ncc-pdp11-its-application-failover.json --port "$(NCC_WATCH_PORT)"
	@$(PYTHON) ./scripts/lab-state.py select "$(NCC_LAB_ROOT)" ncc-failover "$(RESULTS_ROOT)/ncc-pdp11-its-application-failover-$(RUN_ID)"

watch-ncc:
	@test -n "$(NCC_RESULT)" || { printf '%s\n' 'No NCC result was selected. Set NCC_RESULT to the named growing result.' >&2; exit 66; }
	$(PYTHON) ./scripts/ncc-serve-board.py "$(NCC_RESULT)" --topology config/topologies/ncc-pdp11-its-coexistence.json --port "$(NCC_WATCH_PORT)"

view-ncc:
	@test -n "$(NCC_RESULT)" || { printf '%s\n' 'No passing coexistence result is available. Run `make ncc` first or set NCC_RESULT.' >&2; exit 66; }
	$(PYTHON) ./scripts/ncc-serve-board.py "$(NCC_RESULT)" --topology config/topologies/ncc-pdp11-its-coexistence.json --port "$(NCC_VIEW_PORT)" --require-existing

view-ncc-failover:
	@test -n "$(NCC_FAILOVER_RESULT)" || { printf '%s\n' 'No passing failover result is available. Run `make ncc-failover` first or set NCC_FAILOVER_RESULT.' >&2; exit 66; }
	$(PYTHON) ./scripts/ncc-serve-board.py "$(NCC_FAILOVER_RESULT)" --topology config/topologies/ncc-pdp11-its-application-failover.json --port "$(NCC_VIEW_PORT)" --require-existing
