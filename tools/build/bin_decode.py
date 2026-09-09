#!/usr/bin/env python3
"""Decodificador offline del OS `.bin` (ELUP) del Octatrack.

Reimplementa FUN_4007f748 (reversado en Ghidra): quita la cabecera, desofusca el
payload con el cifrado XOR-con-realimentacion y verifica el checksum aditivo — el
MISMO que el firmware comprueba antes de aplicar la actualizacion. Si el checksum
cuadra, la desofuscacion es demostrablemente correcta.

Formato ELUP (big-endian, words de 32 bits):
  word[0]      = magic 0x454C5550 ("ELUP")
  word[1]      = semilla de realimentacion (k inicial)
  word[2..N-2] = payload ofuscado
  word[N-1]    = checksum ofuscado

Constantes (extraidas de la imagen del OS):
  XOR A = 0x9E3B16A2 (variante rotate16)   mezcla C3 = 0x360FA955
  XOR B = 0x764E28CA (variante byteswap)   mezcla C7 = 0xEF4A9AB6
La variante por-word la elige el bit 0x800000 de k (el word cifrado anterior).

Uso: python3 bin_decode.py <os.bin> [-o payload_desofuscado.bin]
"""
import argparse
import struct
from pathlib import Path

MAGIC = 0x454C5550
XOR_A, XOR_B = 0x9E3B16A2, 0x764E28CA
C3, C7 = 0x360FA955, 0xEF4A9AB6
M = 0xFFFFFFFF


def rot16(v):
    return ((v << 16) | (v >> 16)) & M


def bswap(v):
    return (((v & 0xFF) << 24) | ((v & 0xFF00) << 8) |
            ((v & 0xFF0000) >> 8) | (v >> 24)) & M


def decode_word(k, c):
    """Devuelve el word plano dado k (word cifrado previo) y c (word cifrado actual)."""
    if (k & 0x800000) == 0:
        x, mixer = rot16(c ^ XOR_A), C3
    else:
        x, mixer = bswap(c ^ XOR_B), C7
    return (k ^ mixer ^ x) & M


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()

    data = Path(args.file).read_bytes()
    if len(data) % 4:
        print(f"[!] tamaño no múltiplo de 4 ({len(data)}); trunco al último word")
        data = data[: len(data) // 4 * 4]
    words = list(struct.unpack(f">{len(data)//4}I", data))
    n = len(words)

    magic, seed = words[0], words[1]
    print(f"magic   = 0x{magic:08x} ({'ELUP OK' if magic == MAGIC else 'NO ES ELUP'})")
    print(f"seed    = 0x{seed:08x}")
    print(f"words   = {n}  (payload={n-3}, +magic +seed +checksum)")

    k = seed
    acc = 0
    plain = []
    for c in words[2:n-1]:
        p = decode_word(k, c)
        plain.append(p)
        acc = (acc + p) & M
        k = c  # realimentacion = word cifrado

    cksum_cipher = words[n-1]
    expected = decode_word(k, cksum_cipher)  # se descifra igual que un word de payload
    ok = acc == expected
    print(f"\nchecksum calculado (Σ payload) = 0x{acc:08x}")
    print(f"checksum esperado (word final)  = 0x{expected:08x}")
    print(f"VALIDACIÓN: {'✓ COINCIDE — desofuscación correcta' if ok else '✗ no coincide'}")

    if args.out:
        Path(args.out).write_bytes(struct.pack(f">{len(plain)}I", *plain))
        print(f"\npayload desofuscado -> {args.out} ({len(plain)*4} bytes)")
        head = struct.pack(">4I", *plain[:4])
        printable = "".join(chr(b) if 32 <= b < 127 else "." for b in head)
        print(f"primeros 16 bytes: {head.hex()}  '{printable}'")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
