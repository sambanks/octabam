#!/usr/bin/env python3
"""GRANULAR through real FLEX pool reads, the sequencer, both DSPs and MAIN.

The default fixture is made by the firmware itself; no card or hardware is
needed. All images, projects, generated samples, audio and logs stay in out/.
This measures emulator instructions, not hardware cycles or deadlines.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import wave

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import toolpath  # noqa: E402,F401
import blockdump  # noqa: E402
import ot_project as otp  # noqa: E402
import recloop  # noqa: E402
import verify_repitch as source  # noqa: E402
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
SR = 44100
FRAMES = 2 * SR
BASE = 0x40000400
POOL = 0x46C922C4
POOL_STRIDE = 44
STATE_SIZE = 13 * 4 + 4 * 9 * 4
GRAIN_SIZE = 9 * 4
DEFAULTS = (64, 0, 48, 64, 80, 0)
STOCK_DEFAULTS = (64, 0, 0, 127, 0, 79)
STOP_FRAME = 2600


@dataclass(frozen=True)
class Case:
    name: str
    controls: tuple[int, ...] = DEFAULTS
    bits: int = 16
    channels: int = 2
    frames: int = 2000
    tracks: tuple[tuple[int, bool], ...] = ((0, True),)
    effect_load: bool = False


CASES = {
    c.name: c for c in (
        Case("passthrough", STOCK_DEFAULTS, tracks=((0, False),)),
        Case("scan", frames=5000),
        Case("pitch-down", (4, 0, 127, 0, 0, 0)),
        Case("pitch-unity", (64, 0, 127, 0, 0, 0)),
        Case("pitch-up", (124, 0, 127, 0, 0, 0)),
        Case("pitch-semitone", (69, 0, 127, 0, 0, 0)),
        Case("scan-position", (64, 127, 127, 0, 0, 0)),
        Case("mono16", (64, 0, 127, 0, 0, 0), channels=1),
        Case("mono24", (64, 0, 127, 0, 0, 0), bits=24, channels=1),
        Case("stereo24", (64, 0, 127, 0, 0, 0), bits=24),
        Case("density-one", (64, 0, 48, 0, 0, 0)),
        Case("density", (64, 0, 48, 0, 127, 0)),
        Case("size", (64, 0, 0, 0, 127, 0)),
        Case("scatter", (64, 0, 48, 64, 80, 40)),
        Case("scan-end", (64, 0, 48, 127, 80, 0), frames=5000),
        Case("retrigger", frames=9000),
        Case("stop", frames=5000),
        Case("locks", (64, 0, 127, 0, 0, 0), frames=4000),
        Case("scenes", (64, 0, 48, 0, 0, 0), frames=4000),
        Case("lfo", (64, 0, 48, 0, 127, 0), frames=4000),
        Case("mixed", tracks=((0, True), (4, False))),
        Case("two-tracks", frames=4000, tracks=((0, True), (4, True))),
        Case("two-dense", (69, 0, 0, 127, 127, 127), frames=4000,
             tracks=((0, True), (4, True))),
        Case("four-stock", STOCK_DEFAULTS,
             tracks=((0, False), (1, False), (4, False), (5, False))),
        Case("four-tracks", tracks=((0, True), (1, True), (4, True), (5, True))),
        Case("bus-sends", frames=4000, tracks=((0, True), (4, True)), effect_load=True),
        Case("effects-stock", frames=4000, tracks=((0, True), (4, True)), effect_load=True),
        Case("effects", frames=4000, tracks=((0, True), (4, True)), effect_load=True),
    )
}


def require(label: str, ok: bool, detail: str = "") -> None:
    if not ok:
        raise RuntimeError(f"{label}: {detail}")
    print(f"  [PASS] {label}" + (f" -- {detail}" if detail else ""), flush=True)


def run(command: list[str], log: pathlib.Path, timeout: int = 600) -> str:
    with log.open("w") as stream:
        stream.write(" ".join(command) + "\n")
        stream.flush()
        result = subprocess.run(command, cwd=ROOT, stdout=stream,
                                stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"exit {result.returncode}: {log}")
    return log.read_text()


def make_sample(path: pathlib.Path, bits: int, channels: int,
                normal: bool = False) -> None:
    width = bits // 8
    amplitude = round(0.45 * (1 << (bits - 1)))
    raw = bytearray()
    for frame in range(FRAMES):
        segment = frame // SR
        time = (frame % SR) / SR
        for channel in range(channels):
            frequency = (660 if normal else 300) * (segment + 1)
            if channel:
                frequency *= 1.5
            value = round(amplitude * math.sin(2 * math.pi * frequency * time))
            raw.extend(value.to_bytes(width, "little", signed=True))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(SR)
        wav.writeframes(raw)


def prepare_project(template: pathlib.Path, dest: pathlib.Path, case: Case,
                    samples: list[pathlib.Path]) -> None:
    source.SAMPLE_REL = f"AUDIO/{samples[0].name}"
    source.build_project(template, dest, 0, 2, 120, 64, 127)
    for project in dest.glob("project.*"):
        if project.suffix not in (".work", ".strd"):
            continue
        raw = project.read_bytes()
        settings = {
            "SCENE_A_MUTE": 0 if case.name == "scenes" else 1,
            "SCENE_B_MUTE": 0 if case.name == "scenes" else 1,
            "LOAD_24BIT_FLEX": int(case.bits == 24),
        }
        for key, value in settings.items():
            raw, count = re.subn(rb"(?m)^" + key.encode() + rb"=[^\r\n]*",
                                 key.encode() + b"=" + str(value).encode(), raw)
            if not count:
                raise RuntimeError(f"{project}: missing {key}")
        for slot, sample in enumerate(samples[1:], 2):
            raw += (
                f"\r\n[SAMPLE]\r\nTYPE=FLEX\r\nSLOT={slot:03d}\r\n"
                f"PATH=../AUDIO/{sample.name}\r\nTRIM_BARSx100=100\r\n"
                "LOOP_BARSx100=100\r\nBPMx24=2880\r\nTSMODE=2\r\n"
                "LOOPMODE=1\r\nGAIN=48\r\nTRIGQUANTIZATION=-1\r\n"
                "[/SAMPLE]\r\n\r\n"
            ).encode()
        project.write_bytes(raw)
    for markers in dest.glob("markers.*"):
        if markers.suffix not in (".work", ".strd"):
            continue
        raw = bytearray(markers.read_bytes())
        for slot in range(len(samples)):
            at = 0x16 + 784 * slot
            raw[at:at + 784] = struct.pack(">III", 0, FRAMES, 0) + bytes(772)
        raw[-2:] = (sum(raw[0x10:-2]) & 0xFFFF).to_bytes(2, "big")
        markers.write_bytes(raw)
    for bank in dest.glob("bank*.work"):
        def mutate(data: bytearray) -> None:
            for part in range(otp.NPARTS_ALL):
                base = otp.PART_BASE + part * otp.PART_STRIDE
                for track in range(8):
                    data[base + otp.FX1_OFF + track] = 0
                    data[base + otp.FX2_OFF + track] = 0
                    page = base + 9 + 0x11A + track * 24
                    data[page:page + 6] = bytes((32, 32, 32, 0, 0, 0))
                    data[page + 6:page + 12] = bytes((0, 127, 127, 64, 64, 127))
                for track, granular in case.tracks:
                    data[base + otp.MTYPE_OFF + track] = 1
                    slot = 0 if granular or len(samples) == 1 else 1
                    data[base + 0x2D4 + track * 5] = slot
                    controls = case.controls if granular else STOCK_DEFAULTS
                    at = base + source.VALUES_OFF + track * 30 + 6
                    data[at:at + 6] = bytes(controls)
                    setup = base + source.SETUP_OFF + track * 30 + 6
                    data[setup] = 1
                    data[setup + 4] = 0
                if case.name == "lfo":
                    page = base + 9 + 0x11A
                    data[page] = 48
                    data[page + 3] = 24
                    setup = base + 9 + 0x2F2
                    data[setup] = 0
                    data[setup + 3] = 1
                if case.name == "scenes":
                    data[base + 9 + 0x10:base + 9 + 0x12] = bytes((0, 1))
                    for scene, pitch in ((0, 64), (1, 124)):
                        at = base + 9 + 0x662 + scene * 8 * 32
                        data[at:at + 32] = b"\xff" * 32
                        data[at] = pitch
            for pattern in range(16):
                tail = otp.PTRN0 + (pattern + 1) * otp.PTRN_FSTRIDE - 11
                data[tail + 2:tail + 4] = bytes((16, 2))
                for track in range(8):
                    at = otp.trac_off(pattern, track)
                    data[at:at + 64] = bytes(64)
                    data[at + 0x59:at + 0x59 + 64 * 32] = b"\xff" * (64 * 32)
                for track, _ in case.tracks:
                    at = otp.trac_off(pattern, track)
                    data[at + 7] = 1
                    if case.name == "locks":
                        data[at:at + 8] = ((1 << 0) | (1 << 4) | (1 << 8)).to_bytes(8, "big")
                        data[at + 0x59 + 4 * 32] = 124
        otp._bank_write(dest, int(bank.stem[4:]), mutate, guard=False)


def effect_layout(project: pathlib.Path, remix: str, case: Case) -> None:
    selected = registry.remix(remix)
    modules = registry.bound(selected)
    if "SEND" in selected.modules:
        otp.host_rig(project, remix, guard=False)
        for track in range(1, 9):
            otp.set_fx(project, "fx1", track, 0, guard=False)
            if track == 8:
                otp.set_fx(project, "fx2", track, "DELAY",
                           page=[48, 32, 0, 64, 0, 0], guard=False)
                continue
            key = {1: "DELAY SERVER", 5: "REVERB SERVER"}.get(track, "SEND")
            module = modules[key]
            controls = otp.module_defaults(module, {"DEL": 0, "REV": 0})
            otp.set_fx(project, "fx2", track, module.menu.fx2_id,
                       page=controls[:6], page2=controls[6:], guard=False)
    if not case.effect_load:
        return
    if "SEND" in selected.modules:
        if case.name != "bus-sends":
            for track, _ in case.tracks:
                module = modules["CHARACTER"]
                controls = otp.module_defaults(module, {"DRV": 32, "MIX": 80})
                otp.set_fx(project, "fx1", track + 1, module.menu.fx2_id,
                           page=controls[:6], page2=controls[6:], guard=False)
        for track, effect in ((1, "DELAY SERVER"), (5, "REVERB SERVER")):
            module = modules[effect]
            controls = otp.module_defaults(module, {"DEL": 50, "REV": 50})
            otp.set_fx(project, "fx2", track, module.menu.fx2_id,
                       page=controls[:6], page2=controls[6:], guard=False)
    elif "MODULATION" in selected.modules:
        if case.name != "effects-stock":
            for track, effect in ((1, "MODULATION"), (5, "SPECTRUM")):
                module = modules[effect]
                knobs = ({"MODE": 1, "MIX": 80} if effect == "MODULATION"
                         else {"MODE": 1, "FREQ": 80, "RES": 40})
                controls = otp.module_defaults(module, knobs)
                otp.set_fx(project, "fx1", track, module.menu.fx2_id, page=controls[:6],
                           page2=controls[6:], guard=False)
        otp.set_fx(project, "fx2", 1, "DELAY", page=[48, 32, 80, 64, 0, 0], guard=False)
        otp.set_fx(project, "fx2", 5, "DARK REV", page=[64, 64, 32, 64, 64, 80], guard=False)
    else:
        if case.name != "effects-stock":
            otp.set_fx(project, "fx1", 1, "FILTER", page=[64, 64, 16, 0, 0, 0], guard=False)
            otp.set_fx(project, "fx1", 5, "CHORUS", page=[64, 64, 64, 0, 64, 80], guard=False)
        otp.set_fx(project, "fx2", 1, "DELAY", page=[48, 32, 80, 64, 0, 0], guard=False)
        otp.set_fx(project, "fx2", 5, "DARK REV", page=[64, 64, 32, 64, 64, 80], guard=False)


def fader(xf: int) -> str:
    weight = (((-258 * xf) & 0xFFFF) << 16) | ((0x8000 + 258 * xf) & 0xFFFF)
    values = [(0x80003C60 + track * 4, weight.to_bytes(4, "big")) for track in range(10)]
    values.append((0x460D16C8, xf.to_bytes(4, "big")))
    return ";".join(f"{address + index:#x}={value:#x}"
                    for address, data in values for index, value in enumerate(data))


def measure(case: Case, work: pathlib.Path, image: pathlib.Path,
            symbols: dict[str, int], card: pathlib.Path, demand: list[dict]) -> dict:
    bank = (card.parent / "project/bank01.work").read_bytes()
    expected = (bank[otp.PART_BASE + otp.FX1_OFF:otp.PART_BASE + otp.FX1_OFF + 8]
                + bank[otp.PART_BASE + otp.FX2_OFF:otp.PART_BASE + otp.FX2_OFF + 8])
    used_demand = [record for record in demand if case.effect_load and record["id"] in expected]
    dumps = [
        f"{symbols['gr_state']:#x},{STATE_SIZE * 8}={work / 'gr_state.bin'}",
        f"{symbols['gr_page_descriptor']:#x},402={work / 'descriptor.bin'}",
        f"{POOL:#x},{POOL_STRIDE * 2}={work / 'pool.bin'}",
        f"0x80000810,576={work / 'lanes.bin'}",
        f"0x80000ec4,16={work / 'ids.bin'}",
    ]
    command = [
        str(EMU), "--image", str(image), "--card", str(card),
        "--set", "OCTABAM", "--project", "RIG", "--sequencer", "--internal-clock",
        "--frames", str(case.frames), "--load-ms", "90000", "--dsp",
        "--main-level", "64", "--audio-out", str(work / "port"),
        "--mem-dump", ";".join(dumps),
    ]
    if any(granular for _, granular in case.tracks):
        command += ["--step", f"-:call:{symbols['gr_resolve_page']:#x},0x400d31ae,0x400e21e0,0,0"]
    if len(case.tracks) > 1 or case.name == "passthrough":
        command += ["--block-dump", str(work / "blocks.bin")]
    if case.name == "stop":
        midi = work / "stop.mid"
        midi.write_text(f"{STOP_FRAME} fc\n")
        command += ["--midi", str(midi)]
    if case.name == "scenes":
        # Sequencer setup reapplies the Part after the '-' steps; seed A afterwards.
        command += ["--poke", fader(127), "--step", f"2000:poke:{fader(0)}"]
    if case.name == "lfo":
        command += ["--watch-mem", f"{symbols['gr_state'] + 13 * 4 + 4:#x},4"]
    if used_demand:
        peeks = {}
        for record in used_demand:
            for core in (0, 1):
                peeks[core, "X", 0x33DA3 + 8 * record["index"]] = 8
                for home in record["homes"]:
                    key = core, "P", home["addr"]
                    peeks[key] = max(peeks.get(key, 0), len(home["words"]))
        command += ["--dsp-peek", ";".join(
            f"{core}:{space}:{address:x},{length}"
            for (core, space, address), length in peeks.items())]
    text = run(command, work / "port.log")
    require(f"{case.name}: firmware completed every requested frame",
            bool(re.search(rf"frames run : {case.frames}\b.*run ended REACHED", text)))
    marker = re.search(r"port_core0\.wav, .*?transport start at frame (\d+)", text)
    if marker is None:
        raise RuntimeError(f"missing MAIN transport marker: {work / 'port.log'}")
    channels = source.read_wav24(work / "port_core0.wav")
    if len(channels) < 4:
        raise RuntimeError(f"no MAIN L/R slots: {work / 'port_core0.wav'}")
    start = int(marker.group(1))
    audio = [channel[start:] for channel in channels[2:4]]
    require(f"{case.name}: MAIN L/R carry audio",
            all(len(channel) >= case.frames * 16 - 64 and
                max(map(abs, channel), default=0) > 1000 for channel in audio))
    with wave.open(str(work / "main.wav"), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(3)
        wav.setframerate(SR)
        wav.writeframes(b"".join(sample.to_bytes(3, "little", signed=True)
                                for pair in zip(*audio) for sample in pair))
    meter = re.search(r"^cpu .*?(\d+) per frame", text, re.M)
    if meter is None:
        raise RuntimeError(f"missing ColdFire instruction measurement: {work / 'port.log'}")
    state = (work / "gr_state.bin").read_bytes()
    pools = (work / "pool.bin").read_bytes()
    ids = (work / "ids.bin").read_bytes()
    require(f"{case.name}: live FX ids equal the staged project", ids == expected,
            f"live={ids.hex()}, expected={expected.hex()}")
    if any(granular for _, granular in case.tracks):
        descriptor = (work / "descriptor.bin").read_bytes()
        stock = (ROOT / "out/raw/section_3_MAIN_OS.bin").read_bytes()
        original = stock[0x400D31AE - BASE:0x400D31AE - BASE + 402]
        require(f"{case.name}: real-port descriptor retains stock header and enables",
                descriptor[:9] == original[:9] and descriptor[0x142:] == original[0x142:]
                and descriptor[9:18] == b"GRANULAR\0")
        flags, count = struct.unpack_from(">I", pools)[0], struct.unpack_from(">I", pools, 16)[0]
        require(f"{case.name}: firmware loaded the requested sample format",
                (flags & 3) == ((2 if case.bits == 16 else 0) | (case.channels - 1))
                and count == FRAMES, f"flags={flags:#x}, frames={count}")
    track_audio = {}
    if len(case.tracks) > 1 or case.name == "passthrough":
        classes = blockdump.classes(blockdump.read(work / "blocks.bin"))
        for track, granular in case.tracks:
            source_audio = [recloop.track_audio(classes, track + 1, right)
                            for right in (False, True)]
            chain_audio = [recloop.readback_audio(classes, track + 1, right)
                           for right in (False, True)]
            require(f"{case.name}: T{track + 1} source reaches its DSP chain",
                    all(max(map(abs, channel), default=0) > 1000 for channel in source_audio)
                    and all(max(map(abs, channel), default=0) > 100 for channel in chain_audio))
            active = struct.unpack_from(">I", state, track * STATE_SIZE)[0]
            require(f"{case.name}: T{track + 1} selects {'GRANULAR' if granular else 'stock FLEX'}",
                    bool(active) == granular)
            track_audio[track] = {"source": source_audio, "chain": chain_audio}
    return {"audio": audio, "state": state, "log": text,
            "tracks": track_audio, "cpu_per_frame": int(meter.group(1)),
            "demand": used_demand}


def tone(result: dict, expected: float, start: float = 0.25,
         end: float = 0.55, channel: int = 0) -> float:
    values = result["audio"][channel][round(start * SR):round(end * SR)]
    frequency = source.pitch(values)
    cents = 1200 * math.log2(frequency / expected) if frequency > 0 else float("inf")
    require("MAIN pitch matches the requested musical ratio", abs(cents) <= 1,
            f"{frequency:.4f} Hz, target {expected:.4f} Hz, {cents:.3f} cents")
    return frequency


def tone_residual(result: dict, frequency: float, channel: int) -> float:
    values = result["audio"][channel][round(0.25 * SR):round(0.55 * SR)]
    basis = [(math.sin(2 * math.pi * frequency * index / SR),
              math.cos(2 * math.pi * frequency * index / SR))
             for index in range(len(values))]
    offset = sum(values) / len(values)
    sine = 2 * sum(value * pair[0] for value, pair in zip(values, basis)) / len(values)
    cosine = 2 * sum(value * pair[1] for value, pair in zip(values, basis)) / len(values)
    error = sum((value - offset - sine * pair[0] - cosine * pair[1]) ** 2
                for value, pair in zip(values, basis))
    residual = math.sqrt(error / sum(value * value for value in values))
    require(f"MAIN {'LR'[channel]} preserves the unscattered source tone",
            residual <= 0.01, f"relative RMS residual {residual:.6f} <= 0.01")
    return residual


def comparisons(bus: bool) -> dict[str, str]:
    return {"density": "density-one", "size": "density", "scatter": "scan",
            "bus-sends": "two-tracks", "effects-stock": "two-tracks",
            "effects": "bus-sends" if bus else "effects-stock"}


def validate(case: Case, result: dict, prior: dict[str, dict]) -> dict:
    metrics = {
        "cpu_instructions_per_frame": result["cpu_per_frame"],
        "main_peak_24bit": [max(map(abs, channel)) for channel in result["audio"]],
        "main_rms_24bit": [math.sqrt(sum(value * value for value in channel) / len(channel))
                          for channel in result["audio"]],
        "main_clipped_samples": [sum(abs(value) >= 0x7FFFFE for value in channel)
                                 for channel in result["audio"]],
    }
    if not case.effect_load:
        require(f"{case.name}: the dry fixture does not clip MAIN",
                not any(metrics["main_clipped_samples"]),
                f"L/R clipped samples {metrics['main_clipped_samples']}")
    if case.name in ("two-tracks", "four-tracks", "four-stock"):
        frequencies = (660, 990) if case.name == "four-stock" else (300, 450)
        metrics["tone_residual_rms"] = [
            tone_residual(result, frequency, channel)
            for channel, frequency in enumerate(frequencies)]
        for channel, frequency in enumerate(frequencies):
            tone(result, frequency, channel=channel)
    if case.name.startswith("pitch-"):
        ratio = 2 ** ((case.controls[0] - 64) / 60)
        metrics["pitch_hz"] = tone(result, 300 * ratio)
    elif case.name in ("mono16", "mono24", "stereo24"):
        metrics["pitch_hz"] = tone(result, 300)
        tone(result, 300 if case.channels == 1 else 450, channel=1)
    elif case.name == "scan-position":
        metrics["pitch_hz"] = tone(result, 600)
    elif case.name in ("scan", "retrigger"):
        tone(result, 300)
        tone(result, 600, 1.15, 1.45)
        if case.name == "retrigger":
            tone(result, 300, 2.25, 2.55)
    elif case.name == "scan-end":
        end = round(1.4 * SR)
        require("scan-end: audio becomes exactly silent after the bounded grain tail",
                all(channel[end:] and not any(channel[end:]) for channel in result["audio"]))
        position = struct.unpack_from(">I", result["state"], 16)[0]
        require("scan-end: scan saturates at the sample end", position == FRAMES * 256)
    elif case.name == "stop":
        end = STOP_FRAME * 16 + 8192 + 512
        require("MIDI Stop: no audio after the longest possible grain tail",
                all(channel[end:] and not any(channel[end:]) for channel in result["audio"]))
    elif case.name == "locks":
        tone(result, 300, 0.15, 0.4)
        tone(result, 600, 0.65, 0.9)
        tone(result, 300, 1.15, 1.4)
    elif case.name == "scenes":
        tone(result, 300, 0.15, 0.4)
        tone(result, 600, 1.05, 1.35)
    elif case.name == "lfo":
        address = re.escape(f"{prior['symbols']['gr_state'] + 13 * 4 + 4:#x}")
        values = [int(value, 16) for value in re.findall(
            rf"\[{address}\] <- (0x[0-9a-f]+)", result["log"])]
        require("LFO: published pitch changes the rates of newly spawned grains",
                len(set(values)) > 2 and all(32768 <= value <= 131072 for value in values),
                f"{len(set(values))} distinct Q16 rates")
        metrics["distinct_pitch_rates"] = len(set(values))
    if case.name in ("size", "density", "density-one"):
        length, hop, density = struct.unpack_from(">III", result["state"], 24)
        expected_density = 1 + case.controls[4] * 4 // 128
        require(f"{case.name}: SIZE and DENS reach the real renderer",
                length == 64 * (case.controls[2] + 1)
                and density == expected_density and hop == length // expected_density,
                f"length={length}, density={density}, hop={hop}")
        active = sum(struct.unpack_from(">I", result["state"], 13 * 4 + g * GRAIN_SIZE + 16)[0] > 0
                     for g in range(4))
        require(f"{case.name}: real grains follow the requested overlap",
                active == 1 if density == 1 else 3 <= active <= 4,
                f"{active} live grains")
        metrics.update(grain_samples=length, hop_samples=hop, density=density,
                       live_grains=active)
    reference_case = prior["references"].get(case.name)
    if reference_case is not None:
        left, reference = result["audio"][0], prior[reference_case]["audio"][0]
        difference = sum((a - b) ** 2 for a, b in zip(left[SR // 4:SR // 2],
                                                       reference[SR // 4:SR // 2]))
        require(f"{case.name}: MAIN changes relative to {reference_case}", difference > 0)
        metrics["audio_difference_squared"] = difference
    if case.effect_load:
        baseline = prior[reference_case]
        for track, _ in case.tracks:
            if case.name != "effects-stock":
                require(f"{case.name}: T{track + 1} post-FX differs from {reference_case}",
                        result["tracks"][track]["chain"] != baseline["tracks"][track]["chain"])
            require(f"{case.name}: T{track + 1} source remains bit-identical",
                    result["tracks"][track]["source"] == baseline["tracks"][track]["source"])
        peeks = {(int(core), space, int(address, 16)):
                 [int(word, 16) for word in words.split()]
                 for core, space, address, words in re.findall(
                     r"core ([01]) ([XP]):0x([0-9a-f]+):([^\n]*)", result["log"])}
        published = {}
        for record in result["demand"]:
            published[record["key"]] = {}
            for core in (0, 1):
                entry = peeks.get((core, "X", 0x33DA3 + 8 * record["index"]), [])
                require(f"{record['key']}: core {core} has a checksum-published entry",
                        len(entry) == 8 and entry[0] == 0xB0A5ED and entry[7] > 0,
                        f"entry={entry}")
                home = next((home for home in record["homes"] if home["addr"] == entry[3]), None)
                if home is None:
                    raise RuntimeError(f"{record['key']}: unknown published home {entry[3]:#x}")
                words = home["words"]
                require(f"{record['key']}: core {core} binds the built init/proc/span",
                        entry[:5] == [0xB0A5ED, home["init"], home["proc"],
                                      home["addr"], home["addr"] + len(words)])
                code = peeks.get((core, "P", home["addr"]), [])
                end = max((index for index, word in enumerate(words) if word), default=-1) + 1
                require(f"{record['key']}: core {core} contains every built code word",
                        len(code) >= len(words) and code[:end] == words[:end])
                published[record["key"]][core] = {
                    "home": home["addr"], "received": entry[5],
                    "refused": entry[6], "published": entry[7]}
        if published:
            metrics["demand_publication"] = published
    return metrics


def generated_project(root: pathlib.Path) -> pathlib.Path:
    projects = [path.parent for path in root.glob("*/project.work")
                if (path.parent / "bank01.work").is_file()]
    # ot_fresh can retain the NOPROJ placeholder beside the project its panel script created.
    created = [path for path in projects if path.name != "NOPROJ"]
    candidates = created or projects
    if len(candidates) != 1:
        raise RuntimeError(f"expected one firmware-generated project, found {projects}")
    print(f"  [INFO] firmware-generated project: {candidates[0]}", flush=True)
    return candidates[0]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX", "granular"))
    ap.add_argument("--image", type=pathlib.Path, default=ROOT / "out/mainos_bus.bin")
    ap.add_argument("--project", type=pathlib.Path, help="optional private template; default: firmware-generated")
    ap.add_argument("--case", action="append", choices=sorted(CASES))
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "out/granular/port-gate")
    args = ap.parse_args()
    args.image = args.image.resolve()
    args.out = args.out.resolve()
    if args.project is not None:
        args.project = args.project.resolve()
    selected = registry.remix(args.remix)
    if "GRANULAR" not in selected.modules:
        print(f"  [N/A] {args.remix} carries no GRANULAR")
        return 0
    if not EMU.is_file() or not args.image.is_file():
        raise RuntimeError("build the image and port: make bus REMIX=granular; make emu-cf")
    args.out.mkdir(parents=True, exist_ok=True)
    work = pathlib.Path(tempfile.mkdtemp(prefix="run-", dir=args.out))
    print(f"  [INFO] private GRANULAR port outputs: {work}", flush=True)
    image = work / "image.bin"
    shutil.copy2(args.image, image)
    text = subprocess.check_output(
        ["m68k-elf-nm", str(ROOT / "out/platform/runtime/runtime.elf")], text=True)
    symbols = {fields[2]: int(fields[0], 16) for fields in
               (line.split() for line in text.splitlines()) if len(fields) == 3}
    require("built image and symbol table name the same GRANULAR renderer",
            struct.unpack_from(">I", image.read_bytes(), 0x400D6438 - BASE)[0] == symbols["gr_render"])
    template = args.project
    if template is None:
        run([sys.executable, str(ROOT / "tools/hw/ot_fresh.py"), "--image", str(image),
             "--out", str(work / "fresh")], work / "fresh.log")
        template = generated_project(work / "fresh/image")
    if not (template / "project.work").is_file():
        raise RuntimeError(f"no firmware-generated project: {template}")
    upstream = subprocess.check_output(
        ["git", "merge-base", "HEAD", "origin/main"], cwd=ROOT, text=True).strip()
    report = {"remix": args.remix, "upstream_revision": upstream,
              "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
              "fixture": "firmware-generated" if args.project is None else "private template",
              "instrument": "ColdFire port; not hardware timing", "cases": {}}
    bus = "SEND" in selected.modules
    references = comparisons(bus)
    prior = {"symbols": symbols, "references": references}
    demand = []
    if selected.window_demand:
        path = ROOT / "out/dsp/demand_records.json"
        if not path.is_file():
            raise RuntimeError(f"missing built demand records: {path}")
        records = json.loads(path.read_text())
        demand = [dict(records[key], key=key, index=index)
                  for index, key in enumerate(selected.window_demand)]
    names = []

    def include(name: str) -> None:
        if name in names:
            return
        if name in references:
            include(references[name])
        names.append(name)

    requested = args.case or [name for name in CASES
                             if (name != "bus-sends" or bus)
                             and (name != "effects-stock" or not bus)]
    if "bus-sends" in requested and not bus:
        raise RuntimeError(f"bus-sends requires a bus remix, not {args.remix}")
    if "effects-stock" in requested and bus:
        raise RuntimeError("a bus remix uses bus-sends, not effects-stock, as its FX1 comparison")
    for name in requested:
        include(name)
    for name in names:
        case = CASES[name]
        directory = work / name
        directory.mkdir()
        samples = [directory / ("GRAN_SOURCE.wav" if case.tracks[0][1] else "NORMAL.wav")]
        make_sample(samples[0], case.bits, case.channels, not case.tracks[0][1])
        if any(not granular for _, granular in case.tracks) and case.tracks[0][1]:
            samples.append(directory / "NORMAL.wav")
            make_sample(samples[1], case.bits, case.channels, True)
        project = directory / "project"
        prepare_project(template, project, case, samples)
        effect_layout(project, args.remix, case)
        card = directory / "card.img"
        command = [sys.executable, str(ROOT / "tools/emu/ot_emu/stage_card.py"),
                   str(project), "OCTABAM", "RIG", "--tree", str(directory / "tree"),
                   "--out", str(card)]
        for sample in samples:
            command += ["--audio", f"{sample}:AUDIO/{sample.name}"]
        run(command, directory / "stage.log")
        result = measure(case, directory, image, symbols, card, demand)
        if name == "passthrough":
            stock = (ROOT / "out/raw/section_3_MAIN_OS.bin").read_bytes()
            control = bytearray(image.read_bytes())
            for address, size in ((0x400D6438, 4), (0x40031ECE, 6)):
                offset = address - BASE
                control[offset:offset + size] = stock[offset:offset + size]
            path = work / "stock-control.bin"
            path.write_bytes(control)
            comparison = directory / "stock"
            comparison.mkdir()
            baseline = measure(case, comparison, path, symbols, card, demand)
            require("ordinary stereo FLEX source and post-FX audio are bit-identical to stock",
                    result["tracks"] == baseline["tracks"])
            for channel, expected in enumerate((660, 990)):
                tone(result, expected, channel=channel)
                tone(baseline, expected, channel=channel)
            report["stock_cpu_instructions_per_frame"] = baseline["cpu_per_frame"]
            report["passthrough_main_capture_identical"] = result["audio"] == baseline["audio"]
        report["cases"][name] = validate(case, result, prior)
        prior[name] = result
        (work / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"  [PASS] GRANULAR real-firmware gate: {len(report['cases'])} cases; {work}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(f"  [FAIL] verify_granular_port: {error}", file=sys.stderr)
        raise SystemExit(1)
