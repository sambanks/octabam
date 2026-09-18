# octabam — a remixer for the Elektron Octatrack's OS: modules (the
# community's and our own) composed into one image from your own 1.40C.
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
# BUILD is the image's version AND the build tag the panel shows in every
# effect name (tools/build/build_bus.py). No trailing comment on the line:
# make keeps the spaces before a `#` and `make image` then splits its recipe.
BUILD   ?= 79
VERSION ?= OCTABAM$(BUILD)

# Which modules the image carries. `make modules` lists what is available;
# remixes/<name>.py is the selection. bamsep26 is the rig and the default;
# bus is the plain two-server image (BusVerb + BusDelay + send + tempo sync)
# that scripts/refhash.sh proves build changes against.
REMIX   ?= bamsep26
# The project the set gates (verify_set, verify_modedefaults) run under the
# port: OT_PROJECT=<dir> on the command line, else the path in
# ~/.octabam_project (machine-local; card data never enters the repo).
# Without either, the two gates SKIP.
OT_PROJECT ?= $(shell cat $(HOME)/.octabam_project 2>/dev/null)
export OT_PROJECT

# The tools run on bare python3 (stdlib only). The ONE exception is the local
# ColdFire emulator (docs/remixer/EMU.md), which needs `unicorn` from the uv-managed
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
	@test -f out/raw/section_3_MAIN_OS.bin || { echo "missing out/raw/section_3_MAIN_OS.bin (the stock OS every build reads) -- run 'make os' then 'make recon'"; exit 1; }
	REMIX=$(REMIX) BUILD=$(BUILD) XBUS=1 SPEC=1 python3 tools/build/build_bus.py

.PHONY: bus-plain
bus-plain: ## Build without specialization (both servers on both cores)
	REMIX=$(REMIX) python3 tools/build/build_bus.py

.PHONY: image
image: bus ## Repack the build into a card-flashable .bin (see docs/remixer/FLASHING.md); BUILD=N is required
	@test "$(origin BUILD)" != "file" || { echo "make image needs BUILD=N (the version the panel shows; bump it every flash)"; exit 1; }
	@test -f $(SYX) || { echo "missing $(SYX) — run 'make os'"; exit 1; }
	@test -x $(EFT) || { echo "missing $(EFT) — run 'make setup'"; exit 1; }
	EFT_EMIT_CONTAINER=out/elek_$(BUILD).bin $(EFT) \
	  -i $(SYX) -c 3 out/mainos_bus.bin \
	  -V $(VERSION) -o out/OCTATRACK_OS1.40C_$(VERSION).syx
	@test -f out/elek_$(BUILD).bin || { echo; \
	  echo "  the .syx was written but no container came out: $(EFT) was built WITHOUT"; \
	  echo "  tools/patches/elektron-firmware-tool.patch (EFT_EMIT_CONTAINER)."; \
	  echo "  Fix: rm -rf vendor/elektron-firmware-tool; make setup; make image REMIX=$(REMIX) BUILD=$(BUILD)"; exit 1; }
	python3 tools/build/make_bin.py out/elek_$(BUILD).bin \
	  -o out/OCTATRACK_$(VERSION).bin
	@echo
	@echo "  card image: out/OCTATRACK_$(VERSION).bin"
	@echo "  MIDI image: out/OCTATRACK_OS1.40C_$(VERSION).syx"
	@echo "  -> docs/remixer/FLASHING.md before you write either to hardware."

# ------------------------------------------------- audition without flashing --

.PHONY: render
render: ## Build the DEV image and render the bus locally (no hardware)
	REMIX=$(REMIX) DEV=1 XBUS=1 SPEC=1 python3 tools/build/build_bus.py
	python3 tools/harness/send_probe.py --mem out/dsp/mem_dev_A.mem --layout RS

.PHONY: render-delay
render-delay: ## Build the DELAY hatch (all 3 servers real) and render BusDelay locally
	@# No SPEC: a SPEC dump has no delay in payload A (id 0x06 -> SEND alias);
	@# send_probe refuses to run a D layout against one. The delay lives at
	@# P:0x04000 outside the donor region (appended to the .mem dump), so the
	@# full shimmer reverb fits as the downstream sink.
	REMIX=$(REMIX) DEV=1 XBUS=1 python3 tools/build/build_bus.py
	python3 tools/harness/send_probe.py --mem out/dsp/mem_dev_A.mem --layout DS

.PHONY: render-rig
render-rig: bus ## Render ALL EIGHT TRACKS on both cores (the real image, tracks 1-4 on B, 5-8 on A). TRACKS=T1=D,T2=S,.. STEMS=dir
	@# tools/harness/rig_render.py --help for --project/--set/--stem/--skew. The
	@# image is this remix's `make bus`; both payloads are dumped from it.
	python3 tools/harness/rig_render.py --image out/mainos_bus.bin --remix $(REMIX) \
	  $(if $(TRACKS),--tracks "$(TRACKS)",--tracks "T1=D,T2=S,T3=S,T4=S,T5=R,T6=S,T7=S,T8=S" --set T2:-VRB=100 --set T3:-DEL=100 --set T6:-VRB=100 --set T7:-DEL=80 --set T1:-VRB=100) \
	  $(if $(STEMS),--stems $(STEMS),--stems out/test_audio --seconds 4) $(RIGARGS)

.PHONY: verify-twocore
verify-twocore: ## Two-core gate: servers on their REAL cores == the DEV hatch, bit for bit, and under 4 skews (~1 min)
	python3 tools/verify/verify_twocore.py

.PHONY: emu-cf
emu-cf: ## Build and run the headless ColdFire machine (tools/emu/ot_emu) -- boots to the RTOS handoff
	@# --fresh: a cache configured from another source path makes cmake
	@# refuse rather than rebuild.
	@# The host's own architecture, explicitly: an Intel-Homebrew cmake
	@# (/usr/local/bin) configures x86_64 and the port then runs under
	@# Rosetta -- 4.19 s to the handoff against 3.55 s native (17 Sep 2026).
	cmake --fresh -B out/emu -S tools/emu/ot_emu -DCMAKE_OSX_ARCHITECTURES=$$(uname -m) >/dev/null
	cmake --build out/emu -j8 >/dev/null
	./out/emu/ot_emu --image $(if $(IMAGE),$(IMAGE),out/raw/section_3_MAIN_OS.bin)

.PHONY: verify-onebus
verify-onebus: ## THE ONE AUX BUS on both cores: chain, last-live-stage return, MIX passthrough, T8 refusal, no station sends (~2 min)
	python3 tools/verify/verify_onebus.py

.PHONY: verify-midi
verify-midi: ## Local check of note->PITCH interval (DNOTE override, ~40 s)
	python3 tools/verify/verify_midi.py

.PHONY: midi-flash
midi-flash: ## RECOVERY: flash a .syx over MIDI (Startup Menu). make midi-flash PORT=A SYX=downloads/extracted/OCTATRACK_OS1.40C.syx
	@test -n "$(SYX)" || { echo "usage: make midi-flash PORT=A SYX=<file.syx>  (OT: Startup Menu -> TRIG 3 -> READY TO RECEIVE)"; exit 1; }
	$(PY) tools/hw/midi_flash.py $(PORT) $(SYX)
PORT ?= A

.PHONY: port-compare
port-compare: ## One part under the firmware (ot_emu) and under rig_render on the same input: make port-compare PROJECT=dir [IMAGE=out/mainos_bus.bin] [PCARGS='--tone out/o9d/kickAB_late.wav']
	@test -n "$(PROJECT)" || { echo "usage: make port-compare PROJECT=out/o9d/proj_t1eqA [IMAGE=out/mainos_bus.bin REMIX=bamsep26] [PCARGS=...]"; exit 1; }
	python3 tools/harness/port_compare.py --project $(PROJECT) --remix $(REMIX) $(if $(IMAGE),--image $(IMAGE)) $(PCARGS)

.PHONY: reverb
reverb: ## Render a wav through BusVerb: make reverb IN=loop.wav [ARGS='-p MIX=80']
	@test -n "$(IN)" || { echo "usage: make reverb IN=loop.wav [ARGS='--wet --mode all']"; exit 1; }
	python3 tools/harness/render_reverb.py $(IN) $(ARGS)

# ------------------------------------------------------ measure and verify --

.PHONY: cycles
cycles: ## Cycle cost per effect against the measured per-core budget
	python3 tools/build/cycle_count.py

.PHONY: stock-labels
stock-labels: ## Re-ask the emulated firmware what every stock select prints -> tools/remix/stock_labels.json
	$(PY) tools/build/stock_labels.py

.PHONY: modmap
modmap: ## DSP module load map — which bytes land at which P address
	python3 tools/build/dsp_modmap.py

.PHONY: verify
verify: ## Verify the ColdFire menu edits, module ledger (+ burn probe when it fits; it fits since the one-word displaced move, 14 Sep 2026)
	@# FIRST, before the selftest rebuilds every remix over out/mainos_bus.bin
	@# (the boot-verifier trap, CLAUDE.md): a module started from a garbage
	@# instance block must be silent on silence -- the unit's RAM is not zeroed.
	python3 tools/verify/verify_dirtystate.py $(REMIX)
	python3 tools/remix/selftest.py
	python3 tools/verify/verify_slots.py
	python3 tools/verify/verify_initregs.py $(REMIX)
	python3 tools/verify/verify_replaces.py
	python3 tools/build/label_fmt.py
	python3 tools/verify/verify_octakit.py
	python3 tools/verify/verify_midiscenes.py
	REMIX=$(REMIX) python3 tools/verify/verify_dram_boot.py
	@# The four ColdFire-port checks need the .venv (make emu-setup). Without
	@# it they SKIP; with it a failure FAILS (until 16 Sep 2026 `|| echo SKIP`
	@# swallowed every exit code, and verify_modenames had been failing since
	@# image 27 behind a SKIP line).
	@if [ -x .venv/bin/python3 ]; then \
	  .venv/bin/python3 tools/verify/verify_labels.py $(REMIX) && \
	  .venv/bin/python3 tools/verify/verify_modenames.py $(REMIX) && \
	  .venv/bin/python3 tools/verify/verify_ccpage2.py && \
	  .venv/bin/python3 tools/verify/verify_hidden.py $(REMIX); \
	else echo "  [SKIP] labels / mode names / cc page-2 / hidden engines: no .venv (make emu-setup)"; fi
	python3 tools/verify/verify_grains.py $(REMIX)
	@# The station and insert gates: each renders its module through dsp_host
	@# on a scratch image the audition builds (remix-independent; Character's
	@# master path reads the shipping build and SKIPs when it lacks Character).
	@# Not in make check until 16 Sep 2026 (run by hand after each station round).
	python3 tools/verify/verify_character.py
	python3 tools/verify/verify_spectrum.py
	python3 tools/verify/verify_modulation.py
	python3 tools/verify/verify_nimbus.py
	python3 tools/verify/verify_hello.py
	REMIX=$(REMIX) python3 tools/verify/verify_menu.py
	python3 tools/verify/verify_burn.py $(REMIX)
	python3 tools/verify/verify_twocore.py
	python3 tools/verify/verify_onebus.py
	python3 tools/verify/verify_tempo.py $(REMIX)
	@# REPITCH: its hooks through the firmware's own code, its page drawings,
	@# and with OT_PROJECT a live tempo change under the port (SKIPs parts it
	@# cannot run; a remix without REPITCH is a one-line pass).
	python3 tools/verify/verify_repitch.py $(REMIX)
	@# A real project on the built image under the ColdFire port (ids, page-2
	@# delivery, chain audio, the main out); SKIPs without OT_PROJECT (above).
	python3 tools/verify/verify_set.py $(REMIX)
	@# A MODE turned on the panel re-defaults its knobs (the FX1 and FX2
	@# page-2 editors called under the port); SKIPs without OT_PROJECT (above).
	python3 tools/verify/verify_modedefaults.py $(REMIX)

.PHONY: verify-roll
verify-roll: ## Prove an alternate REVERB engine is bit-identical: make verify-roll CAND=cand.asm [REF=modules/busverb/reverb_server.asm]
	@test -n "$(CAND)" || { echo "usage: make verify-roll CAND=<candidate.asm> [REF=modules/busverb/reverb_server.asm]"; exit 1; }
	python3 tools/verify/verify_roll.py $(CAND) $(if $(REF),--ref $(REF))

.PHONY: verify-spectrum-ident
verify-spectrum-ident: ## Prove a rewritten Spectrum is bit-identical to a saved reference: make verify-spectrum-ident SAVE=1 on the tree you trust, then make verify-spectrum-ident
	python3 tools/verify/verify_spectrum_ident.py $(if $(SAVE),ref,check)

.PHONY: verify-delay
verify-delay: ## Prove an alternate DELAY engine is bit-identical: make verify-delay CAND=modules/busdelay/delay_new.asm
	@test -n "$(CAND)" || { echo "usage: make verify-delay CAND=modules/busdelay/delay_new.asm [REF=modules/busdelay/delay_server.asm]"; exit 1; }
	python3 tools/verify/verify_delay.py $(CAND) $(if $(REF),--ref $(REF))

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
	DEV=1 XBUS=1 python3 tools/build/build_bus.py >/dev/null
	python3 tools/verify/verify_bus.py $(if $(SAVE),--save) $(if $(SELFTEST),--selftest)

.PHONY: burn
burn: ## The RIG BURN image: the shipping remix + a cycle-burn knob on SEND's slot 2 (24 cycles/step, every core) -> out/mainos_bus.bin; `make burn-image BUILD=N` packs it
	REMIX=$(REMIX) BUILD=$(BUILD) XBUS=1 SPEC=1 BURN=1 python3 tools/build/build_bus.py

.PHONY: burn-image
burn-image: burn ## Repack the RIG BURN build into a card-flashable .bin (BUILD=N: name it so the panel says which image it is)
	@test -f $(SYX) || { echo "missing $(SYX) — run 'make os'"; exit 1; }
	@test -x $(EFT) || { echo "missing $(EFT) — run 'make setup'"; exit 1; }
	EFT_EMIT_CONTAINER=out/elek_$(BUILD)burn.bin $(EFT) \
	  -i $(SYX) -c 3 out/mainos_bus.bin \
	  -V $(VERSION)B -o out/OCTATRACK_OS1.40C_$(VERSION)B.syx
	python3 tools/build/make_bin.py out/elek_$(BUILD)burn.bin \
	  -o out/OCTATRACK_$(VERSION)B.bin
	@echo
	@echo "  card image: out/OCTATRACK_$(VERSION)B.bin   (the rig + BURN on SEND's slot 2)"
	@echo "  MIDI image: out/OCTATRACK_OS1.40C_$(VERSION)B.syx"

.PHONY: check
check: bus cycles verify ## Everything that can be checked without hardware (the set gates run under the port when OT_PROJECT or ~/.octabam_project names a project)
	@# verify_burn.py shells out to build_bus.py twice -- with and without
	@# BURN=1, neither with XBUS/SPEC -- and each run overwrites
	@# out/mainos_bus.bin. Left alone, `make check` finishes by leaving a
	@# plain probe build at the shipping artifact's path, all green. Rebuild
	@# so the file on disk is the one the checks were about.
	@$(MAKE) --no-print-directory bus >/dev/null
	@echo
	@echo "  all runnable checks passed (a [SKIP] line above names what did not run); out/mainos_bus.bin restored to the shipping build"

.PHONY: modules
modules: ## List the module index and the available remixes
	python3 tools/remix/index.py

.PHONY: remix
remix: ## The remixer: swap effects in and out, dial + hear them, build the image
	$(PY) tools/remix/app.py

.PHONY: emu-setup
emu-setup: ## Provision the remixer deps (unicorn + textual) into .venv via uv
	uv sync --extra emu
	@echo "remixer ready — 'make remix' (docs/remixer/EMU.md for the emulator view)"
	@echo "route A (emu_rtos) also needs the EMAC-fixed Unicorn: make emu-unicorn"

# Route A needs a Unicorn whose ColdFire EMAC multiplies like the MCF5445x
# (stock 2.1.4 halves every fractional-mode product -- RTOS_FORK section
# 10.16). Builds it from the PyPI sdist + tools/patches/unicorn_emac_fractional.patch
# into .venv/lib/unicorn-emac, where emu_bringup picks it up. The .venv's
# Python must be the host's native architecture (arm64 on Apple silicon):
# the script checks, and emu_rtos refuses to run on a stock EMAC.
.PHONY: emu-unicorn
emu-unicorn: ## Build the EMAC-fixed Unicorn library for route A (needs cmake)
	@arch=$$($(PY) -c 'import platform; print(platform.machine())'); host=$$(uname -m); \
	  if [ "$$arch" != "$$host" ]; then echo "$(PY) is $$arch on a $$host host -- recreate .venv with a native Python first (uv python install; uv sync --extra emu)"; exit 1; fi
	scripts/build_unicorn.sh

# The card: build a FAT16 image from a project directory, boot, mount it with
# the firmware's own storage stack and load the project (docs/remixer/EMU.md M4).
#   make emu-card PROJECT=~/octa/backups/<snapshot>/<project> [SET=OCTABAM NAME=RIG]
PROJECT ?=
SET ?= OCTABAM
NAME ?=
.PHONY: emu-card
emu-card: ## Boot with an emulated CF card holding PROJECT and load it
	@test -n "$(PROJECT)" || { echo "usage: make emu-card PROJECT=<project dir> [SET=..] [NAME=..]"; exit 1; }
	$(PY) tools/emu/emu_card.py --project "$(PROJECT)" --set "$(SET)" $(if $(NAME),--name "$(NAME)",)

# Route A: the firmware's own scheduler running (docs/history/RTOS_FORK.md). Exits 0
# when the M6a gate passes: every task created and run once.
.PHONY: emu-rtos
emu-rtos: ## Boot with the card and run the real scheduler to the M6a gate
	@test -n "$(PROJECT)" || { echo "usage: make emu-rtos PROJECT=<project dir> [SET=..] [NAME=..]"; exit 1; }
	$(PY) tools/emu/emu_rtos.py --project "$(PROJECT)" --set "$(SET)" $(if $(NAME),--name "$(NAME)",) --ms 400 --until-gate

# -------------------------------------------------------------------- misc --

.PHONY: disasm
disasm: ## Open radare2 on the decompressed ColdFire MAIN OS
	scripts/disasm.sh

.PHONY: clean
clean: ## Remove build products (keeps downloads/ and vendor/)
	rm -rf out/dsp out/mainos_bus*.bin out/elek_*.bin out/OCTATRACK_*

.PHONY: help
help: ## Show this help
	@echo "octabam — a remixer for the Octatrack's OS"
	@echo
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / \
	  {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo
	@echo "Cold start:  read PLAN.md, then  make setup && make os && make recon && make modules"
	@echo "Modules:     make modules      the index, the compatibility matrix, the remixes"
	@echo "             make check REMIX=<name>   build + every gate for one selection"
	@echo "             make remix        compose a selection interactively"
