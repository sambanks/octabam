#!/usr/bin/env python3
"""Detecta la base address de carga de un firmware raw por correlacion puntero->string.

Idea: si la imagen se carga en la base B, un string en el offset de archivo F vive en
la direccion virtual B+F. Los punteros absolutos de 32 bits en el codigo (immediates,
tablas de punteros) que referencian ese string valdran B+F. Buscando el B que maximiza
el numero de punteros que caen exactamente sobre el inicio de un string, recuperamos B.

Uso: python3 find_base.py <raw.bin> [--top-byte 0x40] [--min-str 5]
"""
import argparse
import struct
from collections import Counter
from pathlib import Path


def find_strings(data, min_len):
    """Devuelve set de offsets de inicio de runs ASCII imprimibles terminados en NUL."""
    starts = {}
    i, n = 0, len(data)
    while i < n:
        b = data[i]
        if 0x20 <= b < 0x7f:
            j = i
            while j < n and 0x20 <= data[j] < 0x7f:
                j += 1
            if j - i >= min_len:
                starts[i] = data[i:j].decode("ascii", "replace")
            i = j
        else:
            i += 1
    return starts


def words_be(data, top_byte):
    """Genera (pos, valor) de words de 32 bits big-endian en offsets pares cuyo byte
    alto == top_byte (region candidata de punteros)."""
    for pos in range(0, len(data) - 3, 2):
        if data[pos] == top_byte:
            yield pos, struct.unpack_from(">I", data, pos)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--top-byte", default="0x40")
    ap.add_argument("--min-str", type=int, default=5)
    ap.add_argument("--csv", help="volcar mapa completo ptr->string a este CSV")
    args = ap.parse_args()
    top = int(args.top_byte, 0)

    data = Path(args.file).read_bytes()
    strings = find_strings(data, args.min_str)
    str_offsets = set(strings)
    print(f"[find_base] {args.file}: {len(data)} bytes, {len(strings)} strings (>= {args.min_str} chars)")
    print(f"[find_base] buscando punteros con byte alto {hex(top)} ...")

    # Voto: por cada puntero P en la region, base implicada = P - F si apunta a un string.
    # Como F < tamano de imagen, para cada P probamos B = P - F solo si (P - B) es un
    # offset de string valido. Equivalente: para cada string F, ¿existe P == B + F?
    # Contamos votos para cada base candidata B = P - F acotando F al rango de la imagen.
    votes = Counter()
    ptrs = list(words_be(data, top))
    n = len(data)
    for _, P in ptrs:
        # base candidata debe dejar todos los offsets dentro de [0, n)
        # Solo consideramos que P apunta a ALGUN string: B = P - F, F en str_offsets
        # Optimizacion: probamos la base "redonda" implicada (P con los bits bajos a 0
        # no sirve). Iteramos strings solo si el conteo de punteros es manejable.
        pass

    # Estrategia eficiente: para un conjunto de bases candidatas (barrido grueso +
    # la hipotesis 0x40000000), contar cuantos punteros caen sobre inicios de string.
    candidates = sorted({top << 24} | {(top << 24) + off for off in (0, 0x1000, 0x2000)})
    # Barrido fino alrededor de top<<24 por si hay un header/offset de carga.
    base_lo = top << 24
    for delta in range(0, 0x20001, 4):
        candidates.append(base_lo + delta)
    candidates = sorted(set(candidates))

    ptr_vals = [P for _, P in ptrs]
    ptr_set = set(ptr_vals)
    best = []
    for B in candidates:
        # cuantos strings F tienen un puntero exacto B+F presente
        hits = sum(1 for F in str_offsets if (B + F) in ptr_set)
        if hits:
            best.append((hits, B))
    best.sort(reverse=True)

    print("\n[find_base] top bases por numero de strings referenciados por puntero exacto:")
    for hits, B in best[:8]:
        print(f"   base 0x{B:08x}  ->  {hits} strings con puntero directo")

    if not best:
        print("   (sin coincidencias; prueba otro --top-byte o revisa endianness)")
        return

    B = best[0][1]
    print(f"\n[find_base] BASE ELEGIDA: 0x{B:08x}")

    matches = [(pos, P, P - B) for pos, P in ptrs if (P - B) in strings]
    print(f"[find_base] {len(matches)} punteros resuelven a inicio de string. Ejemplos:")
    for pos, P, F in matches[:12]:
        s = strings[F][:48].replace("\n", " ")
        print(f"   @0x{pos:06x}: ptr 0x{P:08x} -> file+0x{F:06x} '{s}'")

    if args.csv:
        with open(args.csv, "w") as fh:
            fh.write("ptr_site_vaddr,ptr_value,string_vaddr,file_offset,string\n")
            for pos, P, F in matches:
                s = strings[F].replace('"', '""')
                fh.write(f'0x{B+pos:08x},0x{P:08x},0x{B+F:08x},0x{F:06x},"{s}"\n')
        print(f"[find_base] mapa completo -> {args.csv} ({len(matches)} filas)")


if __name__ == "__main__":
    main()
