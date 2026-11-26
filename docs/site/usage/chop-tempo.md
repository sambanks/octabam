## What it does

This module adds a tempo estimate to LAZY CHOP. After you press [YES] and the slice-count popup closes, a second popup displays the estimated tempo derived from your slices, such as `BPM 115 (58)`. The first number is the best-fit tempo, and the number in parentheses is the closest alternative (a 4:3 or 3:2 ratio, or half/double time). The popup remains on screen until you press any key, and that key still performs its normal action. Nothing is written to the sample.

## How to use it

1. Enable **LAZY CHOP TEMPO** alongside LAZY CHOP in your remix (it requires LAZY CHOP).
2. Chop a recording as usual with LAZY CHOP.
3. Press **[YES]**. The slice count appears first, followed by the BPM popup.
4. Press any key to dismiss the popup; that key still triggers its normal function.

## Reading the popup

- The number before the parentheses is the best fit to the gaps between your chops, scored against a 16th-note and triplet grid with a slight preference toward 120 BPM.
- The number in parentheses is another plausible tempo that fits the spacing, such as a 4:3 or 3:2 ratio or half/double time.
- If you place chops freely rather than along a steady beat, the intervals have no consistent tempo and the estimate may be inaccurate. Swung material has not been tested.

## Related

[ LAZY CHOP ](lazy-chop.md) places the slices; this module only reads them.
