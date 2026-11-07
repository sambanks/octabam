# `character-key` -- CHARACTER with SIDECHAIN_COMPRESSOR's keybus

CHARACTER and SIDECHAIN_COMPRESSOR with the stock effects less SPRING REV, PLATE REV and DARK REV (SIDECHAIN_COMPRESSOR's and CHARACTER's DSP words need their space).

- CHARACTER's KEY = T1..T8 reads the keybus SIDECHAIN_COMPRESSOR's `sctap` hook publishes; `tools/verify/verify_char_keybus.py` renders it.
- Not flashed.

```bash
make image REMIX=character-key BUILD=1
```
