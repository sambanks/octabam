# `arr-row-cap` — ARR ROW CAP

An arrangement holds 256 rows. In stock 1.40C, adding a row with the cursor
on END OF ARR. has no limit. The 257th row is written past the arrangement's
memory, over the next arrangement's name, row count and first row, and the
next save writes it into that arrangement's files. Adding a row anywhere
else in the list already stops at 256 with ROW LIMIT REACHED.

With this module, adding a row at END OF ARR. stops at 256 rows too, with
the same ROW LIMIT REACHED message. Nothing else in the arranger changes.

## How

Stock's insert `0x4009e4c8(row)` has three paths:

- an empty arrangement gets its first row;
- a row inserted before the last checks the count first (`cmpil #255`,
  `bhis` to ROW LIMIT REACHED at `0x4009e5c6`);
- a row added at END OF ARR. (`row == count`) is written at index `count`
  and the count goes up, with no check.

An arrangement's working state is 5652 bytes: 20 bytes, then 256 rows of 22.
So the append that makes row 257 writes past it.

`cap.s` takes the 6 bytes at `0x4009e50c` (the compare that picks the
append) and gives the append the middle path's check before it runs.

A saved arrangement of 256 rows probably loads as 255 (reported, not read
in the code). This module does not change that; it keeps stock's 256.

## Gate

`tools/verify/verify_arr_row_cap.py`, under the port: an arrangement's
working state planted at 255 and then 256 rows, the insert called at END OF
ARR. and in the middle. At 256 both refuse (count unchanged, the next
arrangement's first 22 bytes unchanged, the message shown); at 255 the
append adds row 256.
