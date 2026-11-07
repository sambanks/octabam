# Specs

Contracts a module author or a tool writer codes against. Each page says what is guaranteed and what a client must do; what was measured, and when,
is in the module's README, linked from the top of the page.

| spec | for | module |
|---|---|---|
| [SHARED_SITES.md](SHARED_SITES.md) | choosing how two modules share a stock site | |
| [STORE.md](STORE.md) | a module that saves, loads or copies with a project, or keeps settings in working Parts | [STORE](../../modules/store/README.md) |
| [EVENTS.md](EVENTS.md) | a module that reacts to transport, accepted MIDI, the held-step editor or native copies | [EVENTS](../../modules/events/README.md) |
| [HOOKS.md](HOOKS.md) | a module that shares a stock site with a named partner; adding a bridge | [HOOKS](../../modules/hooks/README.md) |
| [BRAIN.md](BRAIN.md) | a module that declares settings; a tool that reads or writes the brain's files | [BRAIN](../../modules/brain/README.md) |

Specified elsewhere: the module manifest, claims and `Override` in [MODULES.md](../contributing/MODULES.md); the demand loader's staging
area, entry layout and doorbell protocol in [DEMAND_LOADER.md](../contributing/DEMAND_LOADER.md).

A change to an event, a bridge, a register ABI, a setting key or the brain file format changes the spec in the same PR.
