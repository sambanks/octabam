#!/usr/bin/env python3
"""Lossless packed storage against an independent bitstream oracle.

Executes the linked ColdFire codec, including every legal step tuple and
invalid data with valid checksums. Native edits after a retained checkpoint
must remain distinguishable from KEY changes and edit reversions.
"""
def oracle(roots, qualities):
    result = bytearray()
    for lane in range(128):
        r = roots[lane*131:(lane+1)*131]
        state, scale = r[128:130]
        result.append(state*84+scale)
        tokens = []
        for step in range(64):
            d, n, q = r[step], r[64+step], qualities[lane*64+step]
            tokens.append((84 if d == 255 else d)*9+(8 if q == 255 else q))
        # A lane is one 640-bit big-endian integer, independent of the
        # firmware's streaming reservoir and byte-write algorithm.
        result.extend(sum(v << (10*(63-i)) for i, v in enumerate(tokens)).to_bytes(80, 'big'))
    return bytes(result)


def mirror(degree):
    return 255 if degree == 255 else max(0,min(127,12*(degree//7-1)+(0,2,4,5,7,9,11)[degree%7]))


def main():
    from verify_harmony_track_retention import main as track_main
    track_main()


if __name__ == '__main__':
    main()
