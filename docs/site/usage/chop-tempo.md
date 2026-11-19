## What it does

Adds a tempo reading to LAZY CHOP. After you press [YES] and the slice-count popup finishes, a second popup shows the tempo the chops point to, for example `BPM 115 (58)`. The first number is the reading the chops support best; the bracket holds the next plausible one, a 4:3 / 3:2 neighbour, or half or double time. It stays until the next key, and that key still does its own job. Nothing is written to your sample.

## How to use it

1. Enable **LAZY CHOP TEMPO** alongside LAZY CHOP in your remix (it needs LAZY CHOP).
2. Chop a take as usual with LAZY CHOP.
3. Press **[YES]**. The slice count appears first, then the BPM popup.
4. Press any key to close the popup; that key still does what it normally does.

## Reading the popup

- The number before the brackets is the best fit to the gaps between your chops, scored on a 16th / triplet grid with a mild preference near 120 BPM.
- The number in brackets is a neighbour that also fits: a 4:3 or 3:2 reading, or half or double time.
- If you chop at your own pace rather than to a beat, the spacing has no tempo in it and the reading can be wrong. Swung material was not measured.

## Measured / inferred

- On 8thmyth's MKI (build T9, 2026-11-17): a take near 73.5 BPM chopped three times read `BPM 73 (146)`, `73 (147)` and `74 (148)`, each within 1%.
- Offline on 27 takes with a known tempo: 21 were within about 1 BPM in the first or bracketed number (78%).
- Under the port: all 46 recorded takes give the reference's line; a real chop showed `8 SLICES` then `BPM 150 (75)`, still up three seconds later, with the slices unchanged.
- Swung material and chops with ZERO SNAP on were not measured. No unit run of the final integer build yet.

## Related

[ LAZY CHOP ](lazy-chop.md) places the slices; this module only reads them.
