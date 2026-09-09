"""Put every tools/ directory on sys.path.

The tools live in groups -- tools/build, tools/verify, tools/harness,
tools/emu, tools/hw -- and import one another by bare name (`import
send_probe`, `from dsp_modmap import BASE`), as they did when all of them
sat in one directory. A script opens with

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath

(parents[1] is tools/ from a group file). Nothing else is needed: the
`remix` package is found under tools/ itself, and every group directory is
placed right after it, so a group's own module wins over nothing but a
same-named module in another group -- there are none.
"""
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parent
ROOT = TOOLS.parent
GROUPS = ("build", "harness", "emu", "hw", "verify")

_tools = str(TOOLS)
_at = sys.path.index(_tools) + 1 if _tools in sys.path else 0
for _g in reversed(GROUPS):
    _p = str(TOOLS / _g)
    if _p not in sys.path:
        sys.path.insert(_at, _p)
