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
	XBUS=1 SPEC=1 python3 tools/build_bus.py

.PHONY: bus-plain
bus-plain: ## Build without specialization (both servers on both cores)
	python3 tools/build_bus.py

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
	DEV=1 XBUS=1 SPEC=1 python3 tools/build_bus.py
	python3 tools/send_probe.py --mem out/dsp/mem_dev_A.mem --layout RS

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
verify: ## Verify the ColdFire menu edits and the burn probe's integrity
	python3 tools/verify_menu.py
	python3 tools/verify_burn.py

.PHONY: verify-roll
verify-roll: ## Prove an alternate engine is bit-identical: make verify-roll CAND=dsp/reverb_rolled.asm
	@test -n "$(CAND)" || { echo "usage: make verify-roll CAND=dsp/reverb_rolled.asm"; exit 1; }
	python3 tools/verify_roll.py $(CAND)

.PHONY: burn
burn: ## Build the cycle-burn probe (splices burn_block{1,2}.inc into the live engine)
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
	@echo "  all checks passed; out/mainos_bus.bin restored to the shipping build"

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
