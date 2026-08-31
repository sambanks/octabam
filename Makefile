# octabam — custom DSP effects for the Elektron Octatrack MKII
#
# Every target here is a command that was previously an incantation to
# remember. The env-var flags are real and load-bearing; see `make help`.

SHELL   := /bin/bash
SYX     ?= downloads/extracted/OCTATRACK_OS1.40C.syx
EFT     := vendor/elektron-firmware-tool/elektron-firmware-tool
DSP_ASM := vendor/dsp56300/build/source/dsp_host/dsp_asm

# Stamped into the OS version field (max 10 chars) so the unit tells you which
# build it is running. Bump BUILD every time you flash: a unit whose version
# string you cannot map back to a commit is a unit you are guessing about.
BUILD   ?= 001
VERSION ?= OCTABAM$(BUILD)

# Which modules the image carries. `make modules` lists what is available;
# remixes/<name>.py is the selection. chongbong is the shipping one.
REMIX   ?= chongbong

# The tools run on bare python3 (stdlib only). The ONE exception is the local
# ColdFire emulator (docs/EMU.md), which needs `unicorn` from the uv-managed
# `.venv` (the `emu` extra). Prefer that venv when present, else bare python3 —
# where the emulator view degrades to "unavailable" and everything else works.
PY := $(shell [ -x .venv/bin/python3 ] && echo .venv/bin/python3 || echo python3)

.DEFAULT_GOAL := help

# ---------------------------------------------------------------- toolchain --

.PHONY: setup
setup: ## Install/build the toolchain (idempotent)
	scripts/setup.sh

.PHONY: os
os: ## Download the official Elektron OS (you supply your own copy)
	scripts/fetch-os.sh

.PHONY: recon
recon: ## Unpack + static recon -> out/raw/section_3_MAIN_OS.bin
	scripts/analyze.sh

# -------------------------------------------------------------------- build --

.PHONY: bus
bus: ## THE build: one server per core, cross-core bus -> out/mainos_bus.bin
	REMIX=$(REMIX) XBUS=1 SPEC=1 python3 tools/build_bus.py

.PHONY: bus-plain
bus-plain: ## Build without specialization (both servers on both cores)
	REMIX=$(REMIX) python3 tools/build_bus.py

.PHONY: image
image: bus ## Repack the build into a card-flashable .bin (see docs/FLASHING.md)
	@test -f $(SYX) || { echo "missing $(SYX) — run 'make os'"; exit 1; }
	@test -x $(EFT) || { echo "missing $(EFT) — run 'make setup'"; exit 1; }
	EFT_EMIT_CONTAINER=out/elek_$(BUILD).bin $(EFT) \
	  -i $(SYX) -c 3 out/mainos_bus.bin \
	  -V $(VERSION) -o out/OCTATRACK_OS1.40C_$(VERSION).syx
	python3 tools/make_bin.py out/elek_$(BUILD).bin \
	  -o out/OCTATRACK_$(VERSION).bin
	@echo
	@echo "  card image: out/OCTATRACK_$(VERSION).bin"
	@echo "  MIDI image: out/OCTATRACK_OS1.40C_$(VERSION).syx"
	@echo "  -> docs/FLASHING.md before you write either to hardware."

# ------------------------------------------------- audition without flashing --

.PHONY: render
render: ## Build the DEV image and render the bus locally (no hardware)
	REMIX=$(REMIX) DEV=1 XBUS=1 SPEC=1 python3 tools/build_bus.py
	python3 tools/send_probe.py --mem out/dsp/mem_dev_A.mem --layout RS

.PHONY: render-delay
render-delay: ## Build the DELAY hatch (all 3 servers real) and render BongDelay locally
	@# NO SPEC: a SPEC dump has no delay in payload A (id 0x06 -> SEND alias).
	@# Overwrites mem_dev_A.mem -- send_probe refuses to run a D layout
	@# against a SPEC dump, so a stale mix-up dies loudly instead of
	@# rendering a plausible dry passthrough (12 Aug 2026).
	@# NOSHIM=1 is NOT needed since the DEV placement change (12 Aug
	@# evening): the delay lives at P:0x04000 outside the donor region
	@# (appended to the .mem dump; dsp_host has no 8K wall), so the full
	@# shimmer reverb fits as the downstream sink and the delay's growth
	@# budget is payload B's, not the hatch's.
	REMIX=$(REMIX) DEV=1 XBUS=1 python3 tools/build_bus.py
	python3 tools/send_probe.py --mem out/dsp/mem_dev_A.mem --layout DS

.PHONY: verify-midi
verify-midi: ## Local check of note->PITCH interval (DNOTE override, ~40 s)
	python3 tools/verify_midi.py

.PHONY: reverb
reverb: ## Render a wav through ChonVerb: make reverb IN=loop.wav [ARGS='-p MIX=80']
	@test -n "$(IN)" || { echo "usage: make reverb IN=loop.wav [ARGS='--wet --mode all']"; exit 1; }
	python3 tools/render_reverb.py $(IN) $(ARGS)

# ------------------------------------------------------ measure and verify --

.PHONY: cycles
cycles: ## Cycle cost per effect against the measured per-core budget
	python3 tools/cycle_count.py

.PHONY: modmap
modmap: ## DSP module load map — which bytes land at which P address
	python3 tools/dsp_modmap.py

.PHONY: verify
verify: ## Verify the ColdFire menu edits, module ledger (+ burn probe when it fits; it currently SKIPS)
	python3 tools/remix/selftest.py
	python3 tools/verify_slots.py
	REMIX=$(REMIX) python3 tools/verify_menu.py
	python3 tools/verify_burn.py

.PHONY: verify-roll
verify-roll: ## Prove an alternate engine is bit-identical: make verify-roll CAND=modules/chonverb/reverb_lforoll.asm
	@test -n "$(CAND)" || { echo "usage: make verify-roll CAND=modules/chonverb/reverb_lforoll.asm"; exit 1; }
	python3 tools/verify_roll.py $(CAND)

.PHONY: verify-delay
verify-delay: ## Prove an alternate DELAY engine is bit-identical: make verify-delay CAND=modules/bongdelay/delay_new.asm
	@test -n "$(CAND)" || { echo "usage: make verify-delay CAND=modules/bongdelay/delay_new.asm [REF=modules/bongdelay/delay_server.asm]"; exit 1; }
	python3 tools/verify_delay.py $(CAND) $(if $(REF),--ref $(REF))

.PHONY: verify-bus
verify-bus: ## Prove a bus-layout change is behaviour-preserving. STAMP FIRST: make verify-bus SAVE=1
	@# Deliberately NOT part of `make check`. The hashes cover the whole
	@# render -- reverb engine, delay engine and bus together -- so any
	@# voicing change fails it for a reason that has nothing to do with the
	@# bus. It is an on-demand gate around one edit, like verify-roll:
	@#   make verify-bus SAVE=1     <- on the tree you trust, BEFORE the edit
	@#   ...make the bus change...
	@#   make verify-bus            <- every case bit-identical (the tool prints the count)
	@# Needs the DEV hatch: the gate's whole point is exercising layouts that
	@# carry BOTH servers, and only the hatch has a real delay in payload A.
	DEV=1 XBUS=1 python3 tools/build_bus.py >/dev/null
	python3 tools/verify_bus.py $(if $(SAVE),--save) $(if $(SELFTEST),--selftest)

.PHONY: burn
burn: ## Build the flashable cycle-burn probe (p3 = the burn knob, 32 cycles/step)
	XBUS=1 BURN=1 python3 tools/build_bus.py

.PHONY: check
check: bus cycles verify ## Everything that can be checked without hardware
	@# verify_burn.py shells out to build_bus.py twice -- with and without
	@# BURN=1, neither with XBUS/SPEC -- and each run overwrites
	@# out/mainos_bus.bin. Left alone, `make check` finishes by leaving a
	@# plain probe build at the shipping artifact's path, all green. Rebuild
	@# so the file on disk is the one the checks were about.
	@$(MAKE) --no-print-directory bus >/dev/null
	@echo
	@echo "  all runnable checks passed (verify_burn may report SKIPPED above); out/mainos_bus.bin restored to the shipping build"

.PHONY: modules
modules: ## List the module index and the available remixes
	python3 tools/remix/index.py

.PHONY: remix
remix: ## The remix workbench: compose a selection, see what it costs, build it
	$(PY) tools/remix/tui.py

.PHONY: emu-setup
emu-setup: ## Provision the emulator's dependency (unicorn) into .venv via uv
	uv sync --extra emu
	@echo "emulator ready — 'make remix' then 'e' (docs/EMU.md)"

# -------------------------------------------------------------------- misc --

.PHONY: disasm
disasm: ## Open radare2 on the decompressed ColdFire MAIN OS
	scripts/disasm.sh

.PHONY: clean
clean: ## Remove build products (keeps downloads/ and vendor/)
	rm -rf out/dsp out/mainos_bus*.bin out/elek_*.bin out/OCTATRACK_*

.PHONY: help
help: ## Show this help
	@echo "octabam — custom DSP effects for the Octatrack MKII"
	@echo
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / \
	  {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo
	@echo "Cold start:  read PLAN.md, then  make setup && make os && make recon && make bus"
	@echo "Modules:     make modules      (then: make bus REMIX=<name>)"
	@echo "             make remix        compose a selection interactively"
