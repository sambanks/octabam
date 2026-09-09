"""HELLO DRAM -- the reference minimal ColdFire module, and the loader canary.

The DRAM counterpart of `modules/hello` (the reference minimal DSP insert):
one GNU-as unit, `dram=True`, no detours, no pokes, no menu row. The build
links it into the platform runtime, appends it behind octabam's loader and
depacks it at boot; nothing in the OS calls it. What it proves, every
`make check REMIX=hello-dram`:

  * the m68k toolchain assembles and links a unit the way the platform
    expects (`tools/remix/platform_build.py`);
  * the loader boots -- under the ColdFire port the boot detour reaches
    it, its hash gates pass, the stock aPLib depacker lands the window
    equal to the linked image, and the boot goes on to the RTOS handoff
    (`tools/verify/verify_dram_boot.py`, in `make verify`);
  * the only bytes changed inside the OS are the boot site's three-byte
    redirect into the loader (`0x4000050c`).

A real ColdFire module is this plus `Detour`s naming the unit's symbols at
stock sites (`modules/midi-scenes` is the worked example: seven units, 35
detours, two pokes) -- see `modules/_template_cf/` for the skeleton and
docs/remixer/MODULES.md, "Declaring a ColdFire module".
"""

from remix.schema import Kind, Linked, Module

MODULE = Module(
    name="hello-dram",
    key="HELLO DRAM",
    kind=Kind.CF_PATCH,
    doc="Reference minimal ColdFire module: one DRAM unit, no hooks -- the "
        "loader canary.",
    linked=(Linked("hello", "modules/hello-dram/hello.s", dram=True),),
)
