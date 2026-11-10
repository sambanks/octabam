#!/usr/bin/env python3
"""DRUMMER's styles: the written source of styles.inc (the C table drummer.c includes).

    python3 modules/drummer/styles.py          # writes styles.inc, checks every row
    python3 modules/drummer/styles.py --check  # styles.inc is current

Original patterns written for the module. Each style has three written levels, BASIC (CPLX 0),
STANDARD (CPLX 64) and COMPLEX (CPLX 127): CPLX moves from one to the next by bringing in the next
level's hits (and taking out the ones it drops) one at a time, always in the same order. A fill
(VAR, BRK) closes a bar. One character a step: '.' never, '1'..'9' 10..90 %, 'X' always. Rows are
16 steps (4/4) or 12 (12/8). Zones: K kick, S snare, G ghost, HC hat closed, HO hat open, RD ride,
CR crash, TM tom, PC perc (bells, claves, shakers, rims: what the kit puts in PERC). LAYER
(below) gives every style a PERC and a TOM part from STANDARD up.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ZONES = ("K", "S", "G", "HC", "HO", "RD", "CR", "TM", "PC")

# name (4 chars, the knob's display), comment, len, late, swing, BASIC, STANDARD, COMPLEX, FILL
STYLES = [
    ("BRKB", "breakbeat: a two-step break, snare on 2 and 4", 16, 2, 2,
     dict(K="X.........X.....", S="....X.......X...", HC="X.X.X.X.X.X.X.X."),
     dict(K="X.X.......X.....", S="....X..X.X..X...", G="..........3....3", HC="X.X.X.X.X.X.X.X.", HO="..............X."),
     dict(K="X.X.....X.XX..X.", S="....X..X.X..X..X", G=".3.3...3..3.3.3.", HC="XXX.XXX.XXX.XXX.", HO="......X.......X.", PC=".........X......"),
     dict(K="X.......X.......", S="........X.X.XXXX", TM="..........X.X...")),
    ("HHOP", "hip-hop: boom bap, laid back, swung hats", 16, 4, 6,
     dict(K="X.........X.....", S="....X.......X...", HC="X.X.X.X.X.X.X.X."),
     dict(K="X......X..X.....", S="....X.......X...", G=".............3..", HC="X.X.X.X.X.X.X.X.", HO="......X........."),
     dict(K="X..X...X..X..X..", S="....X.......X..X", G=".....3.....3.3..", HC="XXX.XXX.XXX.XXX.", HO="......X.......X.", PC="..X.......X....."),
     dict(K="X.....X.X.......", S="........X...X.XX")),
    ("FUNK", "funk: syncopated kick, ghosts around the backbeat, 16th hats", 16, 1, 2,
     dict(K="X.....X...X.....", S="....X.......X...", HC="X.X.X.X.X.X.X.X."),
     dict(K="X.....X...X..X..", S="....X.......X...", G="..3...3..3....3.", HC="XXXXXXXXXXXXXXXX"),
     dict(K="X.X...X.X.X..X..", S="....X..X.X..X..X", G=".3.3..3.3..3..3.", HC="XXXXXXXXXXXXXXXX", HO="..........X.....", PC="...X.......X...."),
     dict(K="X...X...........", S="........XX.XX.XX", TM="...........X..X.")),
    ("HOUS", "house: four on the floor, claps, open hats off the beat", 16, 0, 3,
     dict(K="X...X...X...X...", HO="..X...X...X...X."),
     dict(K="X...X...X...X...", S="....X.......X...", HC=".X.X.X.X.X.X.X.X", HO="..X...X...X...X."),
     dict(K="X...X...X...X.3.", S="....X.......X...", G="...3.......3....", HC=".X.X.X.X.X.X.X.X", HO="..X...X...X...X.", PC="...X..X....X..X."),
     dict(K="X...X...X...X...", S="........X.X.XXXX")),
    ("JUNG", "jungle / drum'n'bass: a chopped two-step at speed, a ride on top", 16, 1, 1,
     dict(K="X.........X.....", S="....X.......X..."),
     dict(K="X.X.......X.....", S="....X..X.X..X...", HC="X.X.X.X.X.X.X.X."),
     dict(K="X.X....X..XX....", S="....X..X.X..X.XX", G=".3...3.....3....", HC="XXXXXXXXXXXXXXXX", RD="X...X...X...X..."),
     dict(K="X.X.....X.X.....", S="......X.XX.XXXXX", TM="..........X.X...")),
    ("DUB", "dub / reggae: one drop, kick and snare together on 3", 16, 3, 7,
     dict(K="........X.......", S="........X......."),
     dict(K="........X.......", S="........X.......", HC="X.X.X.X.X.X.X.X."),
     dict(K="........X......3", S="....3...X...3...", G="......3.......3.", HC="X.XXX.XXX.XXX.XX", HO="..X...X...X...X.", PC="....X.......X..."),
     dict(K="........X.......", S="........X..X.XXX", TM="..........X.X.X.")),
    ("AFRO", "afrobeat: syncopated kick, busy hats, a bell in PERC, toms", 16, 1, 3,
     dict(K="X.......X.......", S="....X.......X...", HC="X.X.X.X.X.X.X.X.", PC="X..X..X...X.X..."),
     dict(K="X.....X...X..X..", S="....X.......X...", G="..3....3..3...3.", HC="X.XXX.XXX.XXX.XX", HO="......X.......X.", PC="X..X..X...X.X..."),
     dict(K="X..X..X...X..X..", S="....X..3..X.X...", G=".3.3...3.3.3..3.", HC="XXXXXXXXXXXXXXXX", HO="......X.......X.", TM="...X......X....X", PC="X..X..X.X.X.X..."),
     dict(K="X.....X.........", S="........X.XX.XXX", TM="........X.X.X...")),
    ("CLAV", "son clave 3-2: the clave in PERC, a tumbao in TOM, a cascara in RIDE", 16, 0, 2,
     dict(K="X.......X.......", PC="X..X..X...X.X..."),
     dict(K="X.......X.......", HC="X...X...X...X...", TM="......XX......XX", PC="X..X..X...X.X..."),
     dict(K="X..X...X..X.....", G="..3...3...3...3.", RD="X.XX.X.XX.X.X.X.", TM="..X...XX..X...XX", PC="X..X..X...X.X..."),
     dict(K="X...............", TM="........X.XX.XXX", PC="X..X..X..X..X...")),
    ("BOSS", "bossa nova: a dotted kick, the rim (PERC) on the bossa clave", 16, 0, 1,
     dict(K="X..X....X..X....", HC="X.X.X.X.X.X.X.X.", PC="X..X..X...X..X.."),
     dict(K="X..XX..XX..XX..X", HC="X.X.X.X.X.X.X.X.", PC="X..X..X...X..X.."),
     dict(K="X..XX..XX..XX..X", G="....3.......3...", HC="XXXXXXXXXXXXXXXX", PC="X..X..X...X..X.."),
     dict(K="X..XX..XX.......", PC="X..X..X..X.X.X.X")),
    ("BMBE", "bembe 12/8: the standard bell in PERC, the dotted pulse, toms", 12, 0, 0,
     dict(K="X.....X.....", PC="X.X.XX.X.X.X"),
     dict(K="X.....X.....", HC="X..X..X..X..", TM="...X.X.....X", PC="X.X.XX.X.X.X"),
     dict(K="X..X..X.....", G=".3...3...3..", HC="XXXXXXXXXXXX", TM="..XX.X..XX.X", PC="X.X.XX.X.X.X"),
     dict(K="X.....X.....", TM="......X.XXXX")),
    ("ROCK", "rock: kick on 1 and 3, snare on 2 and 4, straight 8ths", 16, 0, 0,
     dict(K="X.......X.......", S="....X.......X...", HC="X.X.X.X.X.X.X.X."),
     dict(K="X.......X.X.....", S="....X.......X...", HC="X.X.X.X.X.X.X.X.", HO="..............X."),
     dict(K="X.X.....X.X..X..", S="....X.......X..X", G=".......3........", HC="X.X.X.X.X.X.X.X.", HO="......X.......X."),
     dict(K="X.......X.......", S="........X.X.X.X.", TM=".........X.X.XXX")),
    ("DISC", "disco: four on the floor, open hats off the beat, 16th hats", 16, 0, 1,
     dict(K="X...X...X...X...", S="....X.......X...", HO="..X...X...X...X."),
     dict(K="X...X...X...X...", S="....X.......X...", HC="X.X.X.X.X.X.X.X.", HO="..X...X...X...X."),
     dict(K="X...X...X...X...", S="....X.......X..3", G=".......3.......3", HC="XXXXXXXXXXXXXXXX", HO="..X...X...X...X.", PC="X..X..X.X..X..X."),
     dict(K="X...X...X...X...", S="........X.X.XXXX", TM="........X.X.X...")),
    ("TECH", "techno: the kick, then off-beat hats, rides and percussion", 16, 0, 0,
     dict(K="X...X...X...X..."),
     dict(K="X...X...X...X...", HC=".X.X.X.X.X.X.X.X", HO="..X...X...X...X."),
     dict(K="X...X...X...X...", S="....X.......X...", HC="XXXXXXXXXXXXXXXX", HO="..X...X...X...X.", RD="X...X...X...X...", PC="...X..X.X..X..X."),
     dict(K="X...X...X...X...", S="........X.X.XXXX")),
    ("TRAP", "trap: half-time snare on 3, sparse kicks, rolling hats", 16, 0, 0,
     dict(K="X.........X.....", S="........X.......", HC="X.X.X.X.X.X.X.X."),
     dict(K="X......X..X.....", S="........X.......", HC="X.X.X.X.X.X.XXXX"),
     dict(K="X..X...X..X..X..", S="........X......3", G="...........3....", HC="XXXXX.XXXXXXXXXX", HO="......X........."),
     dict(K="X.....X.X.......", S="........X.X.X.XX")),
    ("RNB", "r&b / neo-soul: half time, heavy lay-back, ghosts", 16, 5, 7,
     dict(K="X.........X.....", S="........X.......", HC="X.X.X.X.X.X.X.X."),
     dict(K="X.....X...X.....", S="........X.......", G="...3.......3....", HC="X.X.X.X.X.X.X.X."),
     dict(K="X..X..X...X..X..", S="........X.....3.", G=".3.3...3.3.3....", HC="XXX.XXX.XXX.XXX.", HO="..............X.", PC="....X.......X..."),
     dict(K="X.....X.........", S="........X..X.XXX")),
    ("DEMB", "reggaeton dembow: kick in fours, the dembow snare", 16, 0, 1,
     dict(K="X...X...X...X...", S="...X..X....X..X."),
     dict(K="X...X...X...X...", S="...X..X....X..X.", HC="X.X.X.X.X.X.X.X."),
     dict(K="X...X...X...X...", S="...X..X....X..X.", G=".......3.......3", HC="XXXXXXXXXXXXXXXX", PC="..X.......X....."),
     dict(K="X...X...X...X...", S="...X..X.XXXXXXXX")),
    ("SAMB", "samba: the surdo kick, partido alto in PERC, shaker 16ths", 16, 0, 2,
     dict(K="X..XX..XX..XX..X", PC="X.X..X.X..X.X..."),
     dict(K="X..XX..XX..XX..X", HC="XXXXXXXXXXXXXXXX", PC="X.X..X.X..X.X..."),
     dict(K="X..XX..XX..XX..X", S="..X..X.X..X..X.X", HC="XXXXXXXXXXXXXXXX", TM="....X.......X...", PC="X.X..X.X..X.X..."),
     dict(K="X..XX..X........", S="........XXXXXXXX", TM="........X.X.X.X.")),
    ("BAIA", "baiao: the zabumba kick, a triangle in hats", 16, 0, 1,
     dict(K="X..X....X..X....", HC="X.X.X.X.X.X.X.X."),
     dict(K="X..X....X..X....", S="....X.......X...", HC="XXXXXXXXXXXXXXXX", HO="..X...X...X...X."),
     dict(K="X..X..X.X..X..X.", S="....X..X....X..X", G="..3.......3.....", HC="XXXXXXXXXXXXXXXX", HO="..X...X...X...X."),
     dict(K="X..X....X..X....", S="........X.X.XXXX")),
    ("CUMB", "cumbia: the bass drum on 1 and 3, the guiro in PERC, off-beat hats", 16, 0, 1,
     dict(K="X.......X.......", HC="..X...X...X...X.", PC="X.X.X.X.X.X.X.X."),
     dict(K="X.......X.......", S="....X.......X...", HC="..X...X...X...X.", PC="X.XXX.XXX.XXX.XX"),
     dict(K="X..X....X..X....", S="....X..3....X..3", HC="..X...X...X...X.", TM="......X.......X.", PC="X.XXX.XXX.XXX.XX"),
     dict(K="X.......X.......", TM="........X.X.XXXX")),
    ("GARA", "uk garage: two-step kick, a big swing", 16, 2, 8,
     dict(K="X.........X.....", S="....X.......X...", HC="..X...X...X...X."),
     dict(K="X......X..X.....", S="....X.......X...", HC="X.X.X.X.X.X.X.X.", HO="..X...X...X...X."),
     dict(K="X..X...X..X..3..", S="....X..3....X..3", G=".3.....3.3......", HC="X.XXX.XXX.XXX.XX", HO="..X...X...X...X.", PC="...X.......X...."),
     dict(K="X......X..X.....", S="........X.XX.XXX")),
    ("DSTP", "dubstep: half time, the snare on 3, space", 16, 1, 2,
     dict(K="X...............", S="........X......."),
     dict(K="X.........X.....", S="........X.......", HC="X.X.X.X.X.X.X.X."),
     dict(K="X..X......X..X..", S="........X......3", G="...3......3.....", HC="X.XXX.XXX.XXX.XX", HO="......X.......X.", TM="..............XX"),
     dict(K="X.....X.X.X.....", S="........X.X.XXXX")),
    ("SHUF", "blues shuffle 12/8: the shuffle on hats, then the ride", 12, 1, 0,
     dict(K="X.....X.....", S="...X.....X..", HC="X.XX.XX.XX.X"),
     dict(K="X.....X.....", S="...X.....X..", G="..........3.", HC="X.XX.XX.XX.X"),
     dict(K="X....XX.....", S="...X..3..X.3", G=".3....3.....", RD="X.XX.XX.XX.X"),
     dict(K="X.....X.....", S="......XXXXXX", TM="......X.X.XX")),
    ("SIX8", "6/8 afro trance (after gnawa): qraqeb-like triplets in PERC, toms", 12, 0, 0,
     dict(K="X.....X.....", HC="X..X..X..X.."),
     dict(K="X.....X.....", TM="...X.....X..", PC="XX.XX.XX.XX."),
     dict(K="X..X..X..X..", S="...X.....X..", G=".3...3...3..", TM="..XX.X..XX.X", PC="XX.XX.XX.XX."),
     dict(K="X.....X.....", TM="......X.XXXX")),
    ("ELEC", "electro: a drum-machine kick, 16th hats, a cowbell in PERC", 16, 0, 0,
     dict(K="X.....X...X.....", S="....X.......X...", HC="X.X.X.X.X.X.X.X."),
     dict(K="X.....X...X..X..", S="....X.......X...", HC="XXXXXXXXXXXXXXXX", PC="...X......X....."),
     dict(K="X..X..X...X..X.X", S="....X..3....X.3.", G="..........3.....", HC="XXXXXXXXXXXXXXXX", HO="......X.......X.", TM="...........X.X..", PC="...X..X...X....."),
     dict(K="X.....X...X.....", S="........X.X.XXXX", TM="........X.X.X.X.")),
    ("DEEP", "deep house: four on the floor, a heavy shuffle", 16, 1, 8,
     dict(K="X...X...X...X...", S="....X.......X...", HO="..X...X...X...X."),
     dict(K="X...X...X...X...", S="....X.......X...", HC="X.X.X.X.X.X.X.X.", HO="..X...X...X...X."),
     dict(K="X...X...X...X..3", S="....X.......X...", G="...3...3...3...3", HC="XXXXXXXXXXXXXXXX", HO="..X...X...X...X.", PC=".....X.....X..X."),
     dict(K="X...X...X...X...", S="............XXXX")),
    ("MINI", "minimal techno: the kick, a few hats and clicks", 16, 0, 4,
     dict(K="X...X...X...X..."),
     dict(K="X...X...X...X...", HC="..X...X...X...X.", PC=".......X.......X"),
     dict(K="X...X...X...X...", S="....X.......X...", HC="..X...X...X...X.", HO="......X.........", PC="...X...X.X.....X", TM=".............X.."),
     dict(K="X...X...X...X...", PC="........X.X.XXXX")),
    ("AMAP", "amapiano: a 16th shaker, the log drum in TOM", 16, 2, 5,
     dict(K="X...X...X...X...", HC="XXXXXXXXXXXXXXXX"),
     dict(K="X...X...X...X...", S="....X.......X...", HC="XXXXXXXXXXXXXXXX", TM="......X..X....X."),
     dict(K="X...X...X...X...", S="....X..3....X...", G=".......3.......3", HC="XXXXXXXXXXXXXXXX", TM="...X..X..X..X.X.", PC="X..X..X...X..X.."),
     dict(K="X...X...X...X...", TM="........X.XX.XXX")),
    ("FTWK", "footwork / juke: triplet-feel kicks, the snare on 3", 16, 0, 0,
     dict(K="X..X..X...X..X..", S="........X......."),
     dict(K="X..X..X...X..X..", S="........X.......", HC="X.X.X.X.X.X.X.X."),
     dict(K="X..X..X.X.X..X.X", S="....X...X.....X.", HC="XXXXXXXXXXXXXXXX", TM="..........X..X..", PC="...X......X....."),
     dict(K="X.X.X.X.X.X.X.X.", S="........XXXXXXXX")),
    ("HILF", "highlife: a bell in PERC, the kick on 1 and 3, a light backbeat", 16, 0, 2,
     dict(K="X.......X.......", HC="X.X.X.X.X.X.X.X.", PC="X..X..X...X..X.."),
     dict(K="X..X....X..X....", S="....X.......X...", HC="X.X.X.X.X.X.X.X.", PC="X.X.XX.X.X.XX.X."),
     dict(K="X..X..X.X..X....", S="....X..3....X..3", G="..3.......3.....", HC="XXXXXXXXXXXXXXXX", TM="......X.......XX", PC="X.X.XX.X.X.XX.X."),
     dict(K="X...............", S="............XXXX", TM="........X.X.XXXX")),
]


# PERC and TOM through the styles (image 58): the rows below replace or add a
# style's PC / TM at STANDARD (S) and COMPLEX (C); BASIC stays the skeleton.
# The track is mono: a cell on a step where the same level's kick or snare
# always plays never sounds, so emit() drops it (PERC and TOM win over HAT C
# and RIDE, lose to HAT O: drummer.c PRIO). Fills: a tom takes its step from
# the snare; a fill with no tom ends on three (two in 12/8), the snare's steps
# (drummer.c plays them on the snare when the kit has no TOM).
LAYER = {
    "BRKB": dict(S=dict(PC="......6.......6.", TM="...............5"),
                 C=dict(PC=".....5X......5..", TM="...5............")),
    "HHOP": dict(S=dict(PC="..5.......5....."),
                 C=dict(PC="..X..5....X..5..", TM="..............5.")),
    "FUNK": dict(S=dict(PC="...5.......5...."),
                 C=dict(PC="...X...5...X...5", TM=".......4......4.")),
    "HOUS": dict(S=dict(PC="...5...5...5...5"),
                 C=dict(PC="...X..5....X..5.", TM="..........4.....")),
    "JUNG": dict(S=dict(PC=".....5.......5.."),
                 C=dict(PC="...5.......5....", TM="......4.........")),
    "DUB":  dict(S=dict(PC="....5.......5..."),
                 C=dict(TM="...........4....")),
    "ROCK": dict(S=dict(PC=".......5.......5"),
                 C=dict(PC="...5...5...5...5", TM="...........4....")),
    "DISC": dict(S=dict(PC=".5.5.5.5.5.5.5.5")),
    "TECH": dict(S=dict(PC="...5.......5...."),
                 C=dict(TM=".5.....5.5......")),
    "TRAP": dict(S=dict(PC="...5.......5...."),
                 C=dict(PC=".....X.........5", TM="...........4..4.")),
    "RNB":  dict(S=dict(PC="....5.......5..."),
                 C=dict(TM="...........5....")),
    "DEMB": dict(S=dict(PC="..5.......5....."),
                 C=dict(PC="..X...5...X...5.", TM=".......4.......4")),
    "BAIA": dict(S=dict(PC="..5.......5....."),
                 C=dict(PC=".5...5.5...5...5", TM=".....4.......4..")),
    "GARA": dict(S=dict(PC="...5.......5...."),
                 C=dict(TM="......4.........")),
    "DSTP": dict(S=dict(PC="......5.......5."),
                 C=dict(PC="......X...5...X.")),
    "SHUF": dict(S=dict(PC=".....5.....5"),
                 C=dict(PC=".....5.....5")),
    "DEEP": dict(S=dict(PC=".5.5.5.5.5.5.5.5")),
    "FTWK": dict(S=dict(PC="....5.......5..."),
                 C=dict(PC=".5...5.....5....", TM=".......4...4....")),
    "BOSS": dict(C=dict(TM="..........4.....")),
    "SAMB": dict(C=dict(PC=".X....X..X....X.")),
    "ELEC": dict(C=dict(PC=".......X......X.")),
}
TOM_END = {16: 3, 12: 2}           # a fill with no tom: its last steps on toms

# The fill library (image 72): when ORN sends a fill to the library, the family is drawn with these
# weights: the style's written fill, a rudiment (paradiddles, doubles, six-stroke... played around the
# kit), a triplet fill (6/8 feel: 8th triplets, sextuplets) and 3 over 4 (groups of three 16ths; of two
# in 12/8). Styles not named: FILL_DEFAULT.
FILL_DEFAULT = (2, 3, 3, 2)
FILL_COLOUR = {
    "ROCK": (2, 4, 3, 1), "FUNK": (1, 4, 4, 1), "BRKB": (1, 4, 4, 1), "JUNG": (1, 4, 3, 2),
    "HHOP": (2, 3, 3, 2), "RNB": (2, 2, 4, 2), "DUB": (2, 3, 3, 2), "GARA": (2, 3, 3, 2),
    "HOUS": (6, 2, 1, 1), "TECH": (6, 2, 1, 1), "MINI": (7, 1, 1, 1), "DEEP": (6, 2, 1, 1),
    "DISC": (3, 3, 2, 2), "ELEC": (3, 3, 2, 2),
    "AFRO": (1, 3, 5, 1), "SHUF": (1, 3, 5, 1), "SIX8": (1, 3, 5, 1), "BMBE": (1, 3, 5, 1),
    "HILF": (2, 3, 4, 1),
    "CLAV": (2, 3, 2, 3), "BOSS": (3, 3, 2, 2), "SAMB": (2, 3, 2, 3), "BAIA": (2, 3, 2, 3),
    "CUMB": (2, 3, 2, 3), "DEMB": (3, 3, 1, 3),
    "TRAP": (2, 3, 3, 2), "DSTP": (3, 2, 3, 2), "FTWK": (2, 2, 4, 2), "AMAP": (3, 2, 3, 2),
}


def layered(name, n, basic, std, cplx, fill):
    """The style's levels with LAYER, the mono drops, the fill's toms."""
    lv = {"S": dict(std), "C": dict(cplx)}
    for level, rows in LAYER.get(name, {}).items():
        lv[level].update(rows)
    out = [dict(basic)]
    for row in (lv["S"], lv["C"]):
        row = dict(row)
        busy = {i for z in ("K", "S") for i, ch in enumerate(row.get(z, "." * n)) if ch == "X"}
        for z in ("PC", "TM"):
            if z in row:
                row[z] = "".join("." if i in busy else ch for i, ch in enumerate(row[z]))
                if not row[z].strip("."):
                    del row[z]
        out.append(row)
    fill = dict(fill)
    sn = fill.get("S", "." * n)
    if "TM" not in fill:
        k = TOM_END[n]
        fill["TM"] = "." * (n - k) + "".join("X" if ch == "X" else "." for ch in sn[n - k:])
        if not fill["TM"].strip("."):
            del fill["TM"]
    if "TM" in fill:
        fill["S"] = "".join("." if t == "X" else ch for t, ch in zip(fill["TM"], sn))
        if not fill["S"].strip("."):
            del fill["S"]
    out.append(fill)
    return out


def check():
    names = set()
    assert set(FILL_COLOUR) <= {st[0] for st in STYLES}, set(FILL_COLOUR) - {st[0] for st in STYLES}
    for name, _c, n, late, swing, *rows in STYLES:
        assert len(name) <= 4 and name not in names, name
        names.add(name)
        assert set(LAYER.get(name, {})) <= {"S", "C"}, name
        w = FILL_COLOUR.get(name, FILL_DEFAULT)
        assert len(w) == 4 and 0 < sum(w) <= 255, name
        for row in list(rows) + [r for lv in LAYER.get(name, {}).values() for r in [lv]]:
            for z, s in row.items():
                assert z in ZONES, (name, z)
                assert len(s) == n, (name, z, s, len(s))
                assert all(c == "." or c == "X" or c in "123456789" for c in s), (name, z, s)


def c_row(row, z):
    return f'"{row[z]}"' if z in row else "0"


def emit():
    out = ["/* Generated by styles.py: edit that, then `python3 styles.py`. */",
           f"#define DR_N_STYLES {len(STYLES)}",
           "static const Style STYLES[DR_N_STYLES] = {"]
    for name, comment, n, late, swing, *rows in STYLES:
        basic, std, cplx, fill = layered(name, n, *rows)
        out.append(f"    {{   /* {name}: {comment} */")
        out.append("        { " + ", ".join("{ " + ", ".join(c_row(r, z) for z in ZONES) + " }"
                                            for r in (basic, std, cplx)) + " },")
        out.append("        { " + ", ".join(c_row(fill, z) for z in ZONES) + " },")
        w = FILL_COLOUR.get(name, FILL_DEFAULT)
        out.append(f"        {late}, {swing}, {n}, {{ {', '.join(map(str, w))} }} }},")
    out.append("};")
    out.append("static const char *const STYLE_NAMES[DR_N_STYLES] = { "
               + ", ".join(f'"{s[0]}"' for s in STYLES) + " };")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    check()
    text = emit()
    dest = HERE / "styles.inc"
    if "--check" in sys.argv:
        sys.exit(0 if dest.exists() and dest.read_text() == text else "styles.inc is stale: python3 styles.py")
    dest.write_text(text)
    print(f"wrote styles.inc: {len(STYLES)} styles")
