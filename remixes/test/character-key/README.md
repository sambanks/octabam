# `character-key` -- CHARACTER with KEYBUS

CHARACTER and KEYBUS with the stock effects less SPRING REV, PLATE REV and DARK REV (KEYBUS's and CHARACTER's DSP words need their space).

- CHARACTER's KEY = T1..T8 reads KEYBUS's key words; `tools/verify/verify_char_keybus.py` renders it with the words planted.
- Not flashed.

```bash
make image REMIX=character-key BUILD=1
```
