# `testgen` -- TESTGEN

TESTGEN on FX1 beside the stock effects (all but PLATE REV, whose words it takes).

## What is in it

- **TESTGEN** -- [`modules/testgen/README.md`](../../../modules/testgen/README.md).
- the stock effects but PLATE REV, listed so the chooser is otherwise stock's.
- FX1: TESTGEN first, then FX1's ten stock effects. TESTGEN is FX1-only (`Claims.fx1_only`): no FX2 row, and an FX2 instance from an old project passes audio through.

## Build

```bash
make check REMIX=testgen
```
