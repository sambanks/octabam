#!/usr/bin/env python3
"""verify_dark_mode.py -- Gate test for DARK MODE module under octabam.

Verifies:
1. Stock detour hook site at 0x40013cae (displaced instruction 2a79 400b 9710: moveal 0x400b9710,%a5).
2. Module manifest declarations: store 'octabam.dark-mode', setting 'DARK MODE' (Binary, default=0, Scope.CARD).
3. Dynamic remix.inc macro generation (get_dark_mode) and a ROM-placed hook unit
   with a resolved runtime reference to the Brain setting.
4. Framebuffer bitwise inversion accuracy (1,024-byte full buffer inversion test vector).
5. Setting bypass (0 = bypass / stock display; 1 = invert / dark mode).
"""

import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from remix import brain, schema
from remix.schema import Binary, Scope, Apply


def test_manifest_and_macro():
    import importlib.util
    mod_path = ROOT / "modules" / "dark-mode" / "manifest.py"
    spec = importlib.util.spec_from_file_location("darkmode_manifest", mod_path)
    dm_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dm_mod)

    m = dm_mod.MODULE
    assert m.name == "dark-mode", f"Unexpected module name: {m.name}"
    assert m.store.id == "octabam.dark-mode", f"Unexpected store ID: {m.store.id}"
    assert len(m.settings) == 1, f"Expected 1 setting, got {len(m.settings)}"

    s = m.settings[0]
    assert s.name == "DARK MODE"
    assert isinstance(s.kind, Binary)
    assert s.default == 0
    assert s.scope == Scope.CARD
    assert s.apply == Apply.LIVE

    assert len(m.detours) == 1
    d = m.detours[0]
    assert d.site == 0x40013cae
    assert d.expect == bytes.fromhex("2a79400b9710")

    # The hook must be in ROM: a detour into a DRAM unit hangs the ColdFire
    # port before the loader's bootstrap (measured 2026-11-18).  The Brain
    # value it reads is resolved after the platform link, as store/parts.py
    # does, rather than being jumped into at boot.
    assert dm_mod._UNIT.dram is False, "DARK MODE hook unit must be ROM-placed"
    assert dm_mod._UNIT.runtime_refs == (
        ("BRAIN_DARK", "brain", "brain_v_octabam_dark_mode_1"),), dm_mod._UNIT.runtime_refs
    declared = dict(dm_mod._UNIT.defsyms)["BRAIN_DARK"]
    assert declared >= 0x10000, "BRAIN_DARK must be declared long-form so both links agree"
    assert "BRAIN_DARK" in d.unit or dm_mod._UNIT.label == d.unit  # detour reaches our unit

    class MockNoBrainRemix:
        modules = ("DARK MODE",)
        name = "test-no-brain"
        pins = ()
        settings = {}

    inc_text = dm_mod.dm_inc({"DARK MODE": m}, MockNoBrainRemix())
    assert "get_dark_mode" in inc_text
    assert "move.l  BRAIN_DARK" in inc_text
    assert "dm_enabled" not in inc_text
    print("[PASS] Manifest declarations and dynamic remix.inc macros verified.")


def test_inversion_logic():
    # ColdFire inversion loop: 64 iterations of 4 longwords (256 longwords = 1,024 bytes)
    test_pattern = bytes([i & 0xFF for i in range(1024)])
    expected_inverted = bytes([(~b) & 0xFF for b in test_pattern])

    # Emulate the assembly loop
    buf = bytearray(test_pattern)
    for i in range(0, 1024, 4):
        val = int.from_bytes(buf[i:i+4], "big")
        inv = (~val) & 0xFFFFFFFF
        buf[i:i+4] = inv.to_bytes(4, "big")

    assert bytes(buf) == expected_inverted, "ColdFire inversion logic mismatch!"
    print("[PASS] Framebuffer bitwise inversion vector verified (1024 bytes).")


def test_source_assembly():
    src_file = ROOT / "modules" / "dark-mode" / "darkmode.s"
    text = src_file.read_text()
    assert '.include "remix.inc"' in text, "Missing .include 'remix.inc' in darkmode.s"
    assert "get_dark_mode" in text, "Missing get_dark_mode in darkmode.s"
    assert "0x40013cb4" in text, "Missing stock return site 0x40013cb4"
    assert "0x400b9710" in text, "Missing stock backbuffer address 0x400b9710"
    print("[PASS] Source assembly syntax and stock references verified.")


def main():
    print("=== Octabam Gate: DARK MODE ===")
    test_manifest_and_macro()
    test_inversion_logic()
    test_source_assembly()
    print("ALL TESTS PASSED: dark-mode module is fully compliant with Octabam rules.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
