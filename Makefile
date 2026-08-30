LAB_ROOT ?= ../arpanet-redux-lab
ARPANET_ROOT ?= $(LAB_ROOT)/work/arpanet
LINUX_NCP_ROOT ?= $(ARPANET_ROOT)/src/linux-ncp
ITS_ROOT ?= $(LAB_ROOT)/work/its-readdress-src
H316_BIN ?= $(LINUX_NCP_ROOT)/test/simh/BIN/h316
PDP10_KA_BIN ?= $(LAB_ROOT)/work/ka10-simh/BIN/pdp10-ka
RESULTS_ROOT ?= $(LAB_ROOT)/results
NCP_BUILD_RECEIPT ?= $(LINUX_NCP_ROOT)/.brfid-build-receipt.json
ITS_BUILD_RECEIPT ?= $(ITS_ROOT)/.brfid-build-receipt.json
RUN_ID ?= $(shell python3 -c 'import datetime, uuid; print(datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + str(uuid.uuid4()))')

.NOTPARALLEL:

.PHONY: check-source-only check-source-history test test-simh-env verify-assets verify-sources verify-binaries verify-ncp-source build-ncp build-its verify verify-router verify-mixed verify-two-its smoke-router smoke-mixed smoke-two-its

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

smoke-router: verify-router
	./scripts/smoke-router-oracle.sh "$(LINUX_NCP_ROOT)" "$(H316_BIN)" "$(NCP_BUILD_RECEIPT)" "$(RESULTS_ROOT)/router-oracle-$(RUN_ID)"

smoke-mixed: verify-mixed
	./scripts/smoke-its-linux.sh "$(ARPANET_ROOT)" "$(LINUX_NCP_ROOT)" "$(H316_BIN)" "$(PDP10_KA_BIN)" "$(NCP_BUILD_RECEIPT)" "$(RESULTS_ROOT)/its-linux-$(RUN_ID)"

smoke-two-its: verify-two-its
	./scripts/smoke-two-its.sh "$(ARPANET_ROOT)" "$(ITS_ROOT)" "$(H316_BIN)" "$(PDP10_KA_BIN)" "$(ITS_BUILD_RECEIPT)" "$(RESULTS_ROOT)/two-its-telnet-$(RUN_ID)"
