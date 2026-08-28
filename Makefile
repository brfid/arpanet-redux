LAB_ROOT ?= ../brfid-vintage-network-lab
ARPANET_ROOT ?= $(LAB_ROOT)/work/arpanet
LINUX_NCP_ROOT ?= $(ARPANET_ROOT)/src/linux-ncp
H316_BIN ?= $(LINUX_NCP_ROOT)/test/simh/BIN/h316
PDP10_KA_BIN ?= $(LAB_ROOT)/work/ka10-simh/BIN/pdp10-ka
RESULTS_ROOT ?= $(LAB_ROOT)/results
RUN_ID ?= $(shell python3 -c 'import datetime, uuid; print(datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + str(uuid.uuid4()))')

.PHONY: verify-assets verify-sources verify smoke-router smoke-mixed

verify-assets:
	./scripts/verify-assets.sh "$(ARPANET_ROOT)"

verify-sources:
	./scripts/verify-sources.py "$(LAB_ROOT)"

verify: verify-sources verify-assets

smoke-router: verify
	./scripts/smoke-router-oracle.sh "$(LINUX_NCP_ROOT)" "$(RESULTS_ROOT)/router-oracle-$(RUN_ID)"

smoke-mixed: verify
	./scripts/smoke-its-linux.sh "$(ARPANET_ROOT)" "$(LINUX_NCP_ROOT)" "$(H316_BIN)" "$(PDP10_KA_BIN)" "$(RESULTS_ROOT)/its-linux-$(RUN_ID)"
