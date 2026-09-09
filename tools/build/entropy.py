#!/usr/bin/env python3
"""Sliding-window Shannon entropy scanner for firmware blobs.

Alta entropía (~8.0 bits/byte) => zona comprimida o cifrada.
Baja/media entropía => código, tablas, strings, relleno.

El objetivo en Fase 0 es distinguir "comprimido" (factible con
elektron-firmware-tool) de "cifrado fuerte" (mucho más difícil).

Uso:
    python3 entropy.py <archivo> [--window 1024] [--step 512] [--csv out.csv]

Solo depende de numpy (opcionalmente matplotlib para el PNG).
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np


def shannon_entropy(chunk: bytes) -> float:
    if not chunk:
        return 0.0
    counts = np.bincount(np.frombuffer(chunk, dtype=np.uint8), minlength=256)
    probs = counts[counts > 0] / len(chunk)
    return float(-(probs * np.log2(probs)).sum())


def scan(data: bytes, window: int, step: int):
    offsets, values = [], []
    for off in range(0, max(1, len(data) - window + 1), step):
        offsets.append(off)
        values.append(shannon_entropy(data[off:off + window]))
    return np.array(offsets), np.array(values)


def classify(e: float) -> str:
    if e >= 7.5:
        return "COMPRIMIDO/CIFRADO"
    if e >= 6.0:
        return "mixto/empaquetado"
    if e >= 3.0:
        return "codigo/datos"
    return "relleno/estructura"


def summarize(offsets, values):
    if len(values) == 0:
        print("  (archivo demasiado pequeño para la ventana)")
        return
    print(f"  media={values.mean():.3f}  min={values.min():.3f}  max={values.max():.3f}")
    hi = (values >= 7.5).mean() * 100
    print(f"  {hi:.1f}% de ventanas con entropia >= 7.5 (candidato a comprimido/cifrado)")
    # Segmentacion por bandas contiguas
    prev, start = None, 0
    for i, e in enumerate(values):
        band = classify(e)
        if band != prev:
            if prev is not None:
                print(f"    0x{offsets[start]:08x}-0x{offsets[i]:08x}  {prev}")
            prev, start = band, i
    print(f"    0x{offsets[start]:08x}-0x{offsets[-1]:08x}  {prev}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--window", type=int, default=1024)
    ap.add_argument("--step", type=int, default=512)
    ap.add_argument("--csv")
    ap.add_argument("--png")
    args = ap.parse_args()

    data = Path(args.file).read_bytes()
    print(f"[entropy] {args.file}  ({len(data)} bytes, ventana={args.window}, paso={args.step})")
    offsets, values = scan(data, args.window, args.step)
    print(f"  entropia global del archivo completo: {shannon_entropy(data):.3f} bits/byte")
    summarize(offsets, values)

    if args.csv:
        np.savetxt(args.csv, np.column_stack([offsets, values]),
                   fmt=["%d", "%.5f"], delimiter=",", header="offset,entropy", comments="")
        print(f"  CSV -> {args.csv}")

    if args.png:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            plt.figure(figsize=(12, 3))
            plt.plot(offsets, values, lw=0.6)
            plt.axhline(7.5, color="r", ls="--", lw=0.5)
            plt.ylim(0, 8.1)
            plt.xlabel("offset")
            plt.ylabel("entropia (bits/byte)")
            plt.title(Path(args.file).name)
            plt.tight_layout()
            plt.savefig(args.png, dpi=120)
            print(f"  PNG -> {args.png}")
        except ImportError:
            print("  (matplotlib no instalado; omito PNG)", file=sys.stderr)


if __name__ == "__main__":
    main()
