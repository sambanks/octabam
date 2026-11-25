| ARR ROW CAP -- the arranger's row insert refuses an append past 256 rows,
| as it already refuses an insert in the middle.
|
| Stock's insert 0x4009e4c8(row) has three paths. An empty arrangement gets
| row 0. An insert before the last row checks the count (cmpil #255 / bhis
| 0x4009e5c6: ROW LIMIT REACHED). An insert at END OF ARR. (row == count)
| writes row `count` and increments with no check, so the 257th row is
| written past the arrangement's 5652-byte state (20 bytes, then 256 rows of
| 22) onto the next arrangement's name and row count, and saved there.
| Here the append path takes the middle path's check first.
| SPDX-License-Identifier: MIT

        .equ    APPEND,  0x4009e512             | the append, after the displaced compare
        .equ    MIDDLE,  0x4009e554             | the middle insert (its own check first)
        .equ    FULL,    0x4009e5c6             | ROW LIMIT REACHED, then the epilogue

        .text
        .globl  arc_insert
arc_insert:
        mvzw    %d0,%d0                         | displaced: d0 = the row count
        cmpl    %d0,%d3                         | displaced: d3 = the row to insert at
        bnes    1f
        cmpil   #255,%d0                        | the middle path's limit
        bhis    2f
        jmp     APPEND
1:      jmp     MIDDLE
2:      jmp     FULL
