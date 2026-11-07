# `tools/remix/`: the remix engine

The code that turns `modules/<name>/manifest.py` files and a
`remixes/<name>/remix.py` selection into an image and checks it. Composing a remix is
[`docs/guide/COMPOSING.md`](../../docs/guide/COMPOSING.md); writing a module is
[`docs/contributing/MODULES.md`](../../docs/contributing/MODULES.md).

| file | does |
|---|---|
| `schema.py` | what a module and a remix may declare (`Module`, `Remix`, `Gate`, `Linked`, `Detour`, `CavePatch`, `Runtime`, `Store`, `Setting`, `Pin`, ...) |
| `registry.py` | finds every `modules/*/manifest.py` and `remixes/**/remix.py`; no central list |
| `ledger.py` | cross-module resource collisions (FX2 id, declared conflict, every fixed-address write span, kept bytes, grown table, core-private Y, FX2 buffer region, DSP data range), refused by name before a byte is written |
| `dsp_ranges.py` | who owns each DSP data word in a selection (the ledger's DSP data check), and the port census check `verify_set` runs on the shared window |
| `keep.py` | the build's assert that kept stock bytes (`schema.Keep`) still hold stock, before the first write and on the finished image |
| `store.py` | settings resolved for a remix through layers 1 and 2, the remix refusals, the CS1 budget for early settings, each module's `brain.lock` (`docs/specs/BRAIN.md` sections 2 and 4) |
| `brainfile.py` | the brain file: reader, writer, the `.work` / `.strd` pair rule (`docs/specs/BRAIN.md` sections 6.2 and 7) |
| `stock.py` | the stock FX2 effects as rows a remix can keep in the chooser; what a remix harvests |
| `costs.py`, `slot_costs.json` | slot costs measured on a unit per effect, merged from the matrix reports, and the worst-case DSP load of a remix bounded from them (`docs/contributing/COSTS.md`) |
| `rig.py` | a module's category, track range and chooser, derived from the manifests |
| `index.py` | `make modules`, `make docs`: the module table in `README.md` and the remix index |
| `selftest.py` | proves the ledger catches each collision class and every shipped remix is clean |
| `platform_build.py`, `loader.S` | the DRAM platform: every DRAM unit linked as one image, packed and appended after the OS behind the loader (derived from Em's Octakit loader) |
| `pack.py` | the loader payloads' packer (the firmware's aPLib variant, GKA3, ported from Em's encoder); memoised in `out/cache/` |
| `arena.py` | the audio page arena and the pages a remix takes from it for DRAM |
| `grains.py`, `geom.py` | BusDelay's per-build source substitutions (GRAIN count, line geometry) |
| `state.py` | selection, `problems()`, `measure()`, scratch builds; no UI import |
| `audition.py` | render any effect on a source wav, knobs by manifest name; a `__main__` for headless renders |

The DSP-side build itself is `tools/build/build_bus.py`.

## The audition backend, per effect

| effect | path |
|---|---|
| busverb | `tools/harness/render_reverb.py`, its own fingerprinted engine cache |
| busdelay | the DEV hatch (`DEV=1 XBUS=1` → `out/dsp/mem_dev_A.mem`, rebuilt when stale), then `send_probe --layout DS` |
| inserts | a per-insert scratch image (the insert + SEND), dumped to `out/dsp/_audition_<name>_A.mem`; the user's `out/mainos_bus.bin` is saved and restored around the scratch build |
| stock | a dump of the stock image's payload A, `-alloc 1 -audio 0` |

An id absent from an image dispatches to the fallback; `send_probe`'s
SEND-alias guard refuses to measure it. Every render and A/B mark is
journalled to `out/_audition/log.jsonl` (track, effect, source, every
knob).
