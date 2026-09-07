import re, sys
for name in sys.argv[1:]:
    arms, ends = [], []
    for line in open(name):
        m = re.match(r"\s+f\s*(\d+) \[\s*([\d.]+)\] (armcall|endpost)\s+ret=\S+ args=(\S+) (\S+)", line)
        if not m: continue
        f, s, kind, a1, a2 = m.groups(); f = int(f)
        if kind == "armcall": arms.append((f, int(a2, 16)))
        else: ends.append((f, int(a2, 16)))
    pos = [f * 16 + (w & 0xf) for f, w in arms]
    Ls = [l for f, l in ends]
    print(name.split("/")[-1], "arms", len(arms), "ends", len(ends))
    print("  spacings:", [b - a for a, b in zip(pos, pos[1:])])
    print("  lengths :", Ls)
    print("  seams   :", [pos[i + 1] - (pos[i] + Ls[i]) for i in range(min(len(pos) - 1, len(Ls)))])
