# `rig-kits` — The rig + Octakit

`bamsep26` with Octakit (bridged). No LO-FI fix.

## What is in it

- **BusVerb** — an eight-line FDN reverb (ROOM / PLATE / BIG, shimmer, gate, mid/side width) that serves all eight tracks over a cross-core bus. Hosted on one of tracks 5–8.
- **BusDelay** — a multi-mode delay (CLEAN / pitched GRAIN cloud / REVERSE, tape wow, freeze) serving all eight tracks. Hosted on one of tracks 1–4. TIME reads as a tempo division (TEMPO SYNC).
- **Send** — the FX2 effect every other track runs: one SEND knob into the bus. The fallback for any unassigned track.
- **DELAY** (stock) — the stock Echo Freeze delay row, unchanged; it runs on the ColdFire and costs the DSP nothing.
- **Spectrum** (FX1, on FILTER's id) — a filter pedal: SEM LP/BP/HP, Airwindows Capacitor2, formants, the Moog ladder; ENV and LFO onto the cutoff; width. Knobs FREQ RES ENV LDP LSP WDTH / TAME MODE.
- **Character** (FX1, on LO-FI's id) — fold, saturation, tilt, compressor, width; GLUE compression on track 8 by position (the bus return left it 20 Sep 2026). Knobs DRV FOLD TXTR COMP TONE MIX / SAT WDTH.
- **Modulation** (FX1, on CHORUS's id) — chorus / flanger / comb. Knobs RATE DPTH FDBK MIX / DLY MODE TONE SHPE WID.
- **TEMPO SYNC** (Sam Banks) — two ColdFire caves: the tempo, crossfader and note reach the DSP, and BusDelay's TIME draws as a division (1/8, 1/4 …) instead of milliseconds. On the unit since 24 Aug 2026.
- **CC MAP** (Sam Banks) — MIDI CC 62–67 reach the FX2 effect's page-2 knobs (slots 6–11) and CC 68–73 the FX1 effect's; stock reaches only page 1 over MIDI. One ColdFire cave. Confirmed on hardware 13 Sep 2026.
- **OCTAKIT** (Em, [ems-octakit](https://github.com/emuyia/ems-octakit) ot-26914) — 256 Kits per Project in place of 64 bank-tied Parts. MKII: PART opens LOAD KIT, FUNC+PART opens SAVE KIT; MKI: FUNC+MIDI opens LOAD KIT, FUNC+BANK opens SAVE KIT. FUNC+CUE reloads the assigned Kit; Kits have 7-character names; the LOAD/SAVE KIT menus copy/paste/clear/undo, LOAD KIT > UNDO KIT reloads the last loaded Kit; FUNC+PASTE+PART (MKI: FUNC+PASTE+MIDI) on a pasted Pattern also saves its Kit to the next free slot; PTN+FUNC+RIGHT saves the current Kit, copies it and the Pattern to the next free slots and loads the pair; PTN+FUNC+TRIG copies/pastes/clears/undoes inactive Patterns (BANK+TRIG, then BANK+FUNC+TRIG for other Banks). Costs 3.6 % of the flex pool (18.4 s at 16-bit). Old projects migrate their Parts into the first 64 Kit slots on load. A 154,718-byte runtime in DRAM, carried by octabam's loader.
- **SCENES KITS** (Sam Banks) — the bridge that lets CC MAP and Octakit share the MIDI CC dispatch entry: CCs 62–73 CC MAP's, then Octakit's, then stock's. Nothing of its own to use.
- **SCENES P2** (Sam Banks) — scene locks and the crossfader on page 2 of FX1 and FX2: hold a scene and turn a page-2 knob to lock it in that scene (FUNC + turn removes the lock); the fader lerps locked page-2 slots into the DSP frame every frame, a select snapping at the midpoint; locks follow scene copy / paste / clear / undo and travel in the Part (a 144-byte pool at `+0x90522`, midisc's offset, so the ledger refuses SCENES P2 beside MIDI SCENES). One DRAM unit, nine detours. Measured under the port (`verify_scenesp2`); not on hardware (26 Sep 2026, `modules/scenes-p2/README.md`).
- **SCENES P2 KITS** (Sam Banks) — the bridge that lets SCENES P2 and Octakit share the two page-2 editor entries: a held-scene turn writes the lock pool and never enters her wrapper; every other turn reaches her wrapper whole. Nothing of its own to use.
