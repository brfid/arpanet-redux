LAB_ROOT ?= ../arpanet-redux-lab
PYTHON ?= python3
ARPANET_ROOT ?= $(LAB_ROOT)/work/arpanet
LINUX_NCP_ROOT ?= $(ARPANET_ROOT)/src/linux-ncp
ITS_ROOT ?= $(LAB_ROOT)/work/its-readdress-src
NETWORK_UNIX_ROOT ?= $(LAB_ROOT)/work/network-unix-v6
IMP11A_ROOT ?= $(LAB_ROOT)/work/open-simh
H316_BIN ?= $(LINUX_NCP_ROOT)/test/simh/BIN/h316
PDP10_KA_BIN ?= $(LAB_ROOT)/work/ka10-simh/BIN/pdp10-ka
PDP11_BIN ?= $(IMP11A_ROOT)/BIN/pdp11
RESULTS_ROOT ?= $(LAB_ROOT)/results
NCP_BUILD_RECEIPT ?= $(LINUX_NCP_ROOT)/.brfid-build-receipt.json
ITS_BUILD_RECEIPT ?= $(ITS_ROOT)/.brfid-build-receipt.json
RUN_ID ?= $(shell python3 -c 'import datetime, uuid; print(datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + str(uuid.uuid4()))')
PDP11_BASE_ROOT ?= $(LAB_ROOT)/work/unix-v6-install/images/ncp_root.rl01
PDP11_BASE_SWAP ?= $(LAB_ROOT)/work/unix-v6-install/images/ncp_swap.rl01
PDP11_BUILD_ROOT ?= $(RESULTS_ROOT)/pdp11-telnet-build-$(RUN_ID)
PDP11_BUILD_RECEIPT ?= $(PDP11_BUILD_ROOT)/pdp11-build-receipt.json
NCC_ALTERNATE_DURATION ?= 130
NCC_LOOPBACK_DURATION ?= 130
NCC_DIRECT_FORWARD_SECONDS ?= 45

.NOTPARALLEL:

.PHONY: check-source-only check-source-history test test-simh-env verify-assets verify-sources verify-binaries verify-ncp-source verify-pdp11-source build-ncp build-its build-pdp11-telnet verify verify-router verify-mixed verify-two-its verify-pdp11-its verify-ncc-alternate-path verify-ncc-line-loopback smoke-router smoke-mixed smoke-two-its smoke-pdp11-its smoke-ncc-alternate-path smoke-ncc-line-loopback

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
