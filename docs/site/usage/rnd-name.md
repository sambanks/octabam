This module fills a name editor with a random name built from two 64-word
pools (4,096 combinations) when you hold **`[FUNC]`** and press **`[CUE]`**.

## Access

In any supported name editor, hold **`[FUNC]`** and press **`[CUE]`**. The
stock **`[FUNC]` + `[RECORD]`**, **`[PLAY]`**, and **`[STOP]`** shortcuts
(PASTE, CLEAR, COPY NAME) still work as usual. This module is not included in
the standard remixes; build the `rnd-name` remix to use it.

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

- New projects still start with the stock `PROJECT DDMMYY` default until you
  press the shortcut. The date is read from the clock chip.
- Pressing the shortcut again generates a new pair of words.
- Automated verification (`verify_rnd_name`) covers **`[FUNC]` + `[CUE]`** in
  CREATE, SAVE PROJECT AS, and CHOOSE NEW PROJECT NAME. The sample,
  directory, set, Kit, and COPY PROJECT editors are not currently covered by
  automated tests.
