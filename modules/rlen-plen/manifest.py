"""RLEN PLEN -- a recorder length equal to one loop of the track's pattern.

RLEN counts master-clock 16ths (no scale term, 0x4006e3b2 / 0x40006dfc) and
stops at 64, so a 1/4X track cannot record its own 16-bar pattern at a fixed
length; MAX has no length at all (the recording ends at the next recorder
trig, docs/firmware/RECORDER.md 2a), which is why a manual loop needs TRIG
ONE2 and a second press. This module adds RLEN value 65, drawn PLEN: one
press under TRIG ONE + QREC PLEN records exactly the next pass and stops.

One cave, three entries:

  cave    hooked at 0x40006da6, the arm converter's RLEN read (replayed).
          Raw 65 computes L = len x ticks[scale] x 2,646,000 / tempo24,
          rounded to nearest, and rejoins the fixed-RLEN path at 0x40006e18
          with d4 = L (the stock product would overflow past 67 steps).
          Length and scale are read as the sequencer's step function
          0x4009da20 reads them: bank 0x800065bd, pattern 0x800065be,
          pattern record 0x400eb034 + p x 0x8ed8 + b x 0x9b340 (scale +0,
          length -1, PER TRACK flag +1); PER TRACK: the track record
          0x400e21e0 + t x 0x91a + the same offset (+0x50 length, +0x51
          scale). Ticks per step from the sequencer's table 0x400aba50.
  screen  the RECORDING SETUP drawer's push of the stock RLEN formatter
          (0x4002fb10, `move.l d4,-(sp); pea 0x4002f224`) replayed with
          `fmt` pushed instead -- a six-byte poke, not a second hook.
  fmt     fmt(buf, value): 65 -> the stock "PLEN" string (0x400b541c), else
          the stock RLEN formatter (1..64, MAX).

Plus three pokes: the descriptor's RLEN count (E = 0x400d3c74, +0xd2 +
2 x 4) 65 -> 66, which the setup editor clamps by (0x4002efd2), so the
encoder reaches PLEN; and the part validator's hard-coded 64 (0x40002c72 /
0x40002c78) -> 65, which otherwise rewrites a stored 65 to MAX on every bank
load (measured under the port: the file parser 0x400165dc stores 65, the
validator 0x40002c7a wrote 64 over it). Raw 0..64 keep their meaning; saved parts need no
restamp. RECORDER SPACING (hook 0x40006e0c) is bypassed on the PLEN path:
its next-arm model is for chained sequencer passes, and a PLEN take ended by
the next arm is a MAX take anyway.

Not measured: the drawn PLEN text (the port renders the screen; not run),
a manual REC press under the port (the key handler is not located; the
length path is exercised by a sequencer recorder trig, which takes the same
converter), and the PER TRACK branch on hardware.

Assemble: `m68k-elf-as -mcpu=5475 -o plen.o plen_cave.s`; the build
re-assembles, links at the resolved address and compares against the pinned
bytes (the cave is position-independent: the one self-reference is a
pc-relative pea).
"""

from remix.schema import CavePatch, Kind, Module

CONV_HOOK = 0x40006da6
CONV_HOOK_STOCK = bytes.fromhex("712c0002" "5280")   # mvs.b 2(a4),d0; addq.l #1,d0

SCREEN_SITE = 0x4002fb10
SCREEN_STOCK = bytes.fromhex("2f04" "487af710")      # move.l d4,-(sp); pea pc(0x4002f224)
SCREEN_OFF = 0xfa                                    # `screen:` in the cave

RLEN_COUNT = 0x400d3c74 + 0xd2 + 2 * 4               # descriptor entry 8, slot 2, u32

# The part validator (0x40002c6e, run on every bank load and part change)
# clamps the stored RLEN byte with a hard-coded 64: `moveq #64,d1; cmp.l
# d0,d1; bge; moveq #64,d3; move.b d3,1540(a5)`. Both immediates -> 65.
VALIDATOR_CMP = 0x40002c72                           # 7240 -> 7241
VALIDATOR_SET = 0x40002c78                           # 7640 -> 7641

PLEN_CAVE_BYTES = bytes.fromhex(
    "712c0002" "5280"                        # displaced: d0 = raw + 1
    "0c8000000042" "660000ea"                # 66 (raw 65 = PLEN)? else rts
    "4fefffe8" "48d7030f"                    # save d0-d3/a0-a1 (24 bytes)
    "223980001814" "670000d0"                # d1 = tempo24; 0 -> keep (stock MAX)
    "7139800065be" "243c00008ed8" "4c020800" # d0 = pattern x 0x8ed8
    "7539800065bd" "263c0009b340" "4c032800" # d2 = bank x 0x9b340
    "d082" "41f9400eb034"                    # d0 = record offset; a0 = pattern base
    "4a300801" "67000024"                    # PER TRACK flag at +1?
    "242f00a4" "263c0000091a" "4c032800"     # d2 = track x 0x91a (track at 164(sp))
    "d480" "41f9400e21e0"                    # + offset; a0 = track base
    "77302851" "75302850"                    # d3 = scale (+0x51), d2 = length (+0x50)
    "6000000a"
    "77300800" "753008ff"                    # pattern: d3 = scale (+0), d2 = length (-1)
    "6c000004" "4283"                        # scale < 0 -> 0
    "0c8300000006" "6f000004" "7606"         # scale > 6 -> 6
    "0c8200000002" "6c000004" "7402"         # length < 2 -> 2
    "0c8200000040" "6f000004" "7440"         # length > 64 -> 64
    "41f9400aba50" "26303c00" "4c032800"     # d2 = T = length x ticks[scale]
    "203c00285ff0" "2600" "4c410000"         # d0 = q = 2,646,000 / D; d3 = 2,646,000
    "2240" "4c010000" "9680"                 # a1 = q; d3 = r
    "2002" "4c030000"                        # d0 = T x r
    "2601" "e28b" "d083" "4c410000"          # d0 = floor((T r + D/2) / D)
    "2809" "4c024000" "d880"                 # d4 = T x q + d0
    "4cd7030f" "4fef0018" "588f"             # restore, drop the return address
    "4ef940006e18"                           # rejoin the fixed-RLEN path with d4 = L
    "4cd7030f" "4fef0018"                    # keep: restore
    "4e75"                                   # done: rts
    "201f" "2f04" "487a0006" "2f00" "4e75"   # screen: pop ret; push d4; pea fmt; push ret; rts
    "202f0008" "0c8000000041" "66000012"     # fmt: value == 65?
    "203c400b541c" "2f400008" "4ef940013a08" #   sprintf(buf, "PLEN")
    "4ef94002f224")                          #   else the stock RLEN formatter

assert PLEN_CAVE_BYTES[SCREEN_OFF:SCREEN_OFF + 4] == bytes.fromhex("201f2f04")


def emit(addr):
    """No cave bytes (the linked source supplies them); the screen repoint
    and the count."""
    pokes = (
        (SCREEN_SITE, SCREEN_STOCK,
         bytes.fromhex("4eb9") + (addr + SCREEN_OFF).to_bytes(4, "big")),
        (RLEN_COUNT, (65).to_bytes(4, "big"), (66).to_bytes(4, "big")),
        (VALIDATOR_CMP, bytes.fromhex("7240"), bytes.fromhex("7241")),
        (VALIDATOR_SET, bytes.fromhex("7640"), bytes.fromhex("7641")),
    )
    return b"", pokes


MODULE = Module(
    name="rlen-plen",
    key="RLEN PLEN",
    kind=Kind.CF_PATCH,
    doc="ColdFire cave: RLEN value PLEN (past MAX) = one loop of the track's "
        "pattern on its own scale, so TRIG ONE + QREC PLEN records the next "
        "pass and stops.",
    cf_patches=(
        CavePatch(
            label="rlen plen cave",
            cave_addr=None,
            pinned=PLEN_CAVE_BYTES,
            source="modules/rlen-plen/plen_cave.s",
            hook_addr=CONV_HOOK,
            hook_stock=CONV_HOOK_STOCK,
            emit=emit,
            report_note=" (RLEN 65 = PLEN: length := one pattern loop on the track's "
                        "scale; setup screen draws PLEN; count 65 -> 66)",
        ),
    ),
)
