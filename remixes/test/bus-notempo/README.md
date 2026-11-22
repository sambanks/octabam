# `bus-notempo`: bus without TEMPO SYNC's caves

[`bus`](../bus/README.md) with TEMPO SYNC's `CAVE` setting pinned `OFF`. No publish cave is installed and TIME's formatter is linked but not registered (the image keeps the ON build's DRAM layout), so the DSP reads no held note and BusDelay's TIME draws in milliseconds. BusDelay's panel name reads `BusDlyNOC`. This replaces `NOTEMPO=1`, which also dropped every other module's ROM caves. `scripts/refhash.sh` case `notempo`.

```bash
make bus REMIX=test/bus-notempo
```
