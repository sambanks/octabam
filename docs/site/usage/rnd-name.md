Fills a name editor with a random name from two 64-word pools (4,096
joins). Hold **`[FUNC]`** and press **`[CUE]`**.

## Access

In a supported name editor, hold **`[FUNC]`** and press **`[CUE]`**. Stock
**`[FUNC]` + `[RECORD]`**, **`[PLAY]`** and **`[STOP]`** (PASTE, CLEAR,
COPY NAME) stay. Build the test remix `rnd-name` to try it.

## Operation

| Editor | **`[FUNC]` + `[CUE]`** writes |
|---|---|
| NAME THE NEW PROJECT | a date `YYMMDD ` and two words, for example `261014 SWEEPPAD` |
| SAVE PROJECT AS, CHOOSE NEW PROJECT NAME | a date `YYMMDD ` and two words |
| COPY PROJECT (with COPY PROJECT in the remix) | a date `YYMMDD ` and two words |
| SAVE SAMPLE AS | two words, no date |
| NAME THE NEW DIR, NAME THE NEW SET | two words |
| KITS > SAVE KIT | one short word (7 characters at most) |
| RENAME PROJECT, PART, ARR, remarks, card | stock; the chord does nothing |

- Stock still seeds a new project's name with `PROJECT DDMMYY` until the
  chord runs. The date comes from the clock chip.
- Pressing the chord again changes the words.
- CREATE, SAVE PROJECT AS, and CHOOSE NEW PROJECT NAME are proven under
  the port. Sample, directory, set, Kit and COPY PROJECT paths follow the
  same chord on the unit.
