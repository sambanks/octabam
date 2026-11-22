# `bus-tempo-replay`: bus with TEMPO SYNC's cave replaying only

[`bus`](../bus/README.md) with TEMPO SYNC's `CAVE` setting pinned `REPLAY`. The publish cave replays the instructions it displaces and returns, which isolates the hook from the store; TIME's formatter stays. BusDelay's panel name reads `BusDlyRPL`. This replaces `TEMPOCAVE=replay`, which replaced every module's hooked cave. `scripts/refhash.sh` case `tempocave-replay`.

```bash
make bus REMIX=test/bus-tempo-replay
```
