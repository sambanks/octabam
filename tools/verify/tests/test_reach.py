"""The path classifier, against a fake registry and a fake dependency graph:
no manifests, no firmware."""
import json
import os
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import reach

MAKE_BASE = """\
BUILD ?= 79
define need-remix
@test -n "$(REMIX)"
endef
.PHONY: bus
bus: ## the build
\tpython3 tools/build/build_bus.py
verify-shared: ## shared
\tpython3 tools/remix/selftest.py
\tpython3 tools/verify/verify_knob_clicks.py
verify-remix: ## per remix
\tpython3 tools/verify/verify_menu.py
\tpython3 tools/verify/verify_set.py
accept: ## runner
\tpython3 tools/verify/acceptance.py
ci-dsp: ## ci
\tscripts/vendor.sh dsp56300
render: ## a tool
\tpython3 tools/harness/render_reverb.py
"""


def ctx(make_head=MAKE_BASE, make_base=MAKE_BASE):
    deps = {
        "tools/build/build_bus.py": {"tools/remix/schema.py", "tools/build/dsp_modmap.py"},
        "tools/remix/schema.py": set(),
        "tools/build/dsp_modmap.py": set(),
        "tools/remix/selftest.py": {"tools/remix/schema.py", "tools/build/stock_labels.py"},
        "tools/verify/verify_knob_clicks.py": {"tools/harness/send_probe.py"},
        "tools/verify/verify_menu.py": {"tools/remix/schema.py"},
        "tools/verify/verify_set.py": {"tools/hw/ot_project.py", "tools/emu/emu_bringup.py"},
        "tools/verify/verify_character.py": {"tools/harness/send_probe.py"},
        "tools/verify/verify_burn.py": {"tools/harness/rig_render.py"},
        "tools/harness/rig_render.py": {"tools/harness/send_probe.py"},
        "tools/harness/pressure.py": {"tools/harness/rig_render.py"},
        "tools/verify/verify_docs.py": {"tools/remix/index.py"},
        "tools/hw/bcr2000.py": {"tools/remix/schema.py"},
        "tools/harness/render_reverb.py": {"tools/harness/send_probe.py"},
    }
    return reach.Context(
        module_key={"character": "CHARACTER", "miniverb": "MINIVERB", "orphan": "ORPHAN", "send": "SEND"},
        remixes_of={"CHARACTER": ["bamsep26", "usb"], "MINIVERB": ["miniverb"], "ORPHAN": [], "SEND": ["bamsep26", "usb"]},
        gate_owners={"tools/verify/verify_character.py": ["CHARACTER"], "tools/verify/verify_burn.py": ["SEND"]},
        remixes=["bamsep26", "miniverb", "usb"],
        exists=lambda path: path not in ("modules/gone", "remixes/gone", "remixes/test/gone"),
        deps=deps,
        shared_scripts=reach.recipe_scripts(make_head, "verify-shared") | {"tools/verify/verify_docs.py"},
        remix_scripts=reach.recipe_scripts(make_head, "verify-remix"),
        gate_shared={"tools/verify/verify_character.py": True, "tools/verify/verify_burn.py": False},
        make_base=make_base, make_head=make_head)


SHARED_ALL = 'make check-shared REMIXES="bamsep26 miniverb usb"'
REMIX_ALL = ["make check-remix REMIX=bamsep26", "make check-remix REMIX=miniverb", "make check-remix REMIX=usb"]
EVERY = [SHARED_ALL] + REMIX_ALL
ACCEPT_ALL = 'make accept REMIXES="bamsep26 miniverb usb" STRESS_SOURCE=${STRESS_SOURCE}'
# The floor is the cover: bamsep26 carries CHARACTER and SEND, miniverb
# MINIVERB; usb adds nothing bamsep26 has not.
SHARED = 'make check-shared REMIXES="bamsep26 miniverb"'
REMIX = ["make check-remix REMIX=bamsep26", "make check-remix REMIX=miniverb"]
COVER = [SHARED] + REMIX
ACCEPT = 'make accept REMIXES="bamsep26 miniverb" STRESS_SOURCE=${STRESS_SOURCE}'
IDENTITY = "python3 tools/verify/image_identity.py --base ${BASE}"
BUS = "python3 tools/verify/verify_bus.py --base ${BASE}"
BUILD = ["make test-acceptance", "scripts/refhash.sh check", BUS, IDENTITY, SHARED]


def commands(paths, accept_runs_check=False, c=None):
    return [cmd for _, cmd, _ in reach.plan(reach.classify(paths, c or ctx()), accept_runs_check)]


def note(path, c=None):
    return reach.classify([path], c or ctx())[0][2]


class DefaultRemixTests(unittest.TestCase):
    """QUICK checks octabam, and only it, for every module it carries."""

    def quick(self, remixes_of, remixes):
        return reach.Context(
            module_key={"character": "CHARACTER", "miniverb": "MINIVERB"}, remixes_of=remixes_of, gate_owners={},
            remixes=remixes, deps={}, shared_scripts=(), remix_scripts=(), quick=True, test_remixes=(),
            make_base=MAKE_BASE, make_head=MAKE_BASE)

    def test_a_module_octabam_carries_is_checked_on_octabam_alone(self):
        c = self.quick({"CHARACTER": ["bamsep26", "octabam", "usb"], "MINIVERB": ["miniverb"]},
                       ["bamsep26", "miniverb", "octabam", "usb"])
        self.assertEqual(c.carriers(["bamsep26", "octabam", "usb"]), ["octabam"])
        self.assertEqual(c.carriers(["miniverb"]), ["miniverb"])
        self.assertEqual(c.carriers(["bamsep26", "usb"]), ["bamsep26", "usb"])

    def test_octabam_is_the_floor_and_the_cover_stands_in_without_it(self):
        both = self.quick({"CHARACTER": ["bamsep26", "octabam"], "MINIVERB": ["miniverb"]}, ["bamsep26", "miniverb", "octabam"])
        self.assertEqual(both.floor, ["octabam"])
        without = self.quick({"CHARACTER": ["bamsep26"], "SEND": ["bamsep26"], "MINIVERB": ["miniverb"]}, ["bamsep26", "miniverb"])
        self.assertEqual(without.floor, ["bamsep26"])

    def test_full_checks_every_carrier_and_the_cover(self):
        c = reach.Context(module_key={"character": "CHARACTER"}, remixes_of={"CHARACTER": ["bamsep26", "octabam"]},
                          gate_owners={}, remixes=["bamsep26", "octabam"], deps={}, shared_scripts=(),
                          remix_scripts=(), quick=False, test_remixes=(), make_base=MAKE_BASE, make_head=MAKE_BASE)
        self.assertEqual(c.carriers(["bamsep26", "octabam"]), ["bamsep26", "octabam"])
        self.assertEqual(c.floor, ["bamsep26"])


class ModuleAndRemixTests(unittest.TestCase):
    def test_module_reaches_every_remix_that_carries_it(self):
        # the shared half scoped to the module's own shared gates
        self.assertEqual(commands(["modules/character/engine.asm"]),
                         ['make check-shared REMIXES="bamsep26 usb" MODULES="CHARACTER"',
                          'make check-remix REMIX=bamsep26 MODULES="CHARACTER"', 'make check-remix REMIX=usb MODULES="CHARACTER"',
                          'make accept REMIXES="bamsep26 usb" STRESS_SOURCE=${STRESS_SOURCE}'])

    def test_accept_runs_the_checks_of_the_remixes_it_accepts(self):
        self.assertEqual(commands(["modules/character/engine.asm"], accept_runs_check=True),
                         ['make accept REMIXES="bamsep26 usb" STRESS_SOURCE=${STRESS_SOURCE}'])
        cmds = commands(["modules/miniverb/a.asm", "tools/verify/verify_character.py"], accept_runs_check=True)
        self.assertEqual(cmds, ['make check-shared REMIXES="bamsep26 usb" MODULES="CHARACTER"',
                                "make accept REMIX=miniverb STRESS_SOURCE=${STRESS_SOURCE}"])

    def test_submodule_pin_is_the_module(self):
        self.assertEqual(commands(["modules/miniverb/upstream"]),
                         ['make check-shared REMIXES="miniverb" MODULES="MINIVERB"', 'make check-remix REMIX=miniverb MODULES="MINIVERB"', "make accept REMIX=miniverb STRESS_SOURCE=${STRESS_SOURCE}"])

    def test_module_no_remix_carries_is_the_selftests_refusal(self):
        self.assertIn("no remix carries", note("modules/orphan/manifest.py"))
        self.assertEqual(commands(["modules/orphan/manifest.py"]), ["python3 tools/remix/selftest.py"])

    def test_removed_module_directory_runs_nothing_and_says_so(self):
        self.assertIn("removed module directory", note("modules/gone/manifest.py"))
        self.assertEqual(commands(["modules/gone/manifest.py"]), [])

    def test_unknown_but_present_module_directory_is_the_floor(self):
        self.assertEqual(commands(["modules/mystery/manifest.py"]), COVER)

    def test_template_runs_nothing(self):
        self.assertEqual(commands(["modules/_template/manifest.py"]), [])

    def test_remix_selection_and_readme(self):
        self.assertEqual(commands(["remixes/miniverb/remix.py"]),
                         ["make check REMIX=miniverb", "make accept REMIX=miniverb STRESS_SOURCE=${STRESS_SOURCE}"])
        self.assertEqual(commands(["remixes/miniverb/README.md"]), ["python3 tools/verify/verify_docs.py"])
        self.assertEqual(commands(["modules/miniverb/README.md"]), ["python3 tools/verify/verify_docs.py"])

    def test_one_remix_stays_make_check(self):
        self.assertEqual(commands(["remixes/miniverb/remix.py"])[0], "make check REMIX=miniverb")

    def test_removed_remix_runs_the_selftest_and_the_index(self):
        self.assertIn("removed remix", note("remixes/gone/remix.py"))
        self.assertEqual(commands(["remixes/gone/remix.py"]),
                         ["python3 tools/verify/verify_docs.py", "python3 tools/remix/selftest.py"])
        self.assertEqual(commands(["remixes/test/gone/remix.py"]),
                         ["python3 tools/verify/verify_docs.py", "python3 tools/remix/selftest.py"])
        self.assertEqual(commands(["remixes/gone/README.md"]), ["python3 tools/verify/verify_docs.py"])

    def test_test_remix_selection_and_readme(self):
        self.assertEqual(commands(["remixes/test/miniverb/remix.py"]),
                         ["make check REMIX=miniverb", "make accept REMIX=miniverb STRESS_SOURCE=${STRESS_SOURCE}"])
        self.assertEqual(commands(["remixes/test/miniverb/README.md"]), ["python3 tools/verify/verify_docs.py"])


class DependencyTests(unittest.TestCase):
    def test_the_build_and_what_it_imports_reach_refhash_identity_and_the_shared_half(self):
        for p in ("tools/build/build_bus.py", "tools/remix/schema.py", "tools/build/dsp_modmap.py", "dsp/probe.asm"):
            self.assertEqual(commands([p]), BUILD, p)
        self.assertIn("the build", note("tools/remix/schema.py"))
        self.assertIn("identity", note("tools/remix/schema.py"))

    def test_a_shared_gate_reaches_the_shared_half_only(self):
        for p in ("tools/verify/verify_knob_clicks.py", "tools/remix/selftest.py", "tools/build/stock_labels.py"):
            self.assertEqual(commands([p]), [SHARED], p)
        self.assertIn("shared half", note("tools/build/stock_labels.py"))

    def test_a_per_remix_gate_reaches_the_covers_per_remix_halves_only(self):
        for p in ("tools/verify/verify_menu.py", "tools/verify/verify_set.py", "tools/hw/ot_project.py", "tools/emu/emu_bringup.py"):
            self.assertEqual(commands([p]), REMIX, p)
        self.assertIn("the cover (2 of 3 remixes)", note("tools/verify/verify_menu.py"))

    def test_a_manifest_gate_reaches_its_owners(self):
        # remix_arg=False: the owners' shared gates, for the owners' remixes
        self.assertEqual(commands(["tools/verify/verify_character.py"]),
                         ['make check-shared REMIXES="bamsep26 usb" MODULES="CHARACTER"'])
        # remix_arg=True: the owners' per-remix halves
        self.assertEqual(commands(["tools/verify/verify_burn.py"]),
                         ['make check-remix REMIX=bamsep26 MODULES="SEND"', 'make check-remix REMIX=usb MODULES="SEND"'])
        # once=True: run by the shared half, scoped to its owners
        c = ctx()
        c.gate_once = {"tools/verify/verify_burn.py": True}
        self.assertEqual(commands(["tools/verify/verify_burn.py"], c=c),
                         ['make check-shared REMIXES="bamsep26 usb" MODULES="SEND"'])
        self.assertIn("a gate of SEND", note("tools/verify/verify_burn.py"))

    def test_a_harness_file_reaches_what_runs_it(self):
        # send_probe: the knob census (shared), Character's gate (shared), the burn (SEND's remixes), the acceptance machinery via pressure
        cmds = commands(["tools/harness/send_probe.py"])
        self.assertIn("make test-acceptance", cmds)
        self.assertIn(ACCEPT, cmds)
        # rig_render also runs under verify_burn (SEND's gate, bamsep26 + usb): usb's check is not
        # among the cover's accepts, so it stays
        self.assertEqual(commands(["tools/harness/rig_render.py"], accept_runs_check=True),
                         ["make test-acceptance", 'make check-remix REMIX=usb MODULES="SEND"', ACCEPT])

    def test_a_file_no_gate_depends_on_reaches_nothing(self):
        for p in ("tools/hw/bcr2000.py", "tools/harness/render_reverb.py", "tools/hw/new_tool.py"):
            self.assertEqual(commands([p]), [], p)
            self.assertEqual(note(p), "no gate depends on it", p)

    def test_the_docs_renderer_reaches_verify_docs_as_a_shared_gate(self):
        self.assertEqual(commands(["tools/remix/index.py"]), [SHARED])

    def test_a_verifier_nothing_runs_is_named(self):
        self.assertEqual(commands(["tools/verify/verify_roll.py"]), [])
        self.assertIn("own make target", note("tools/verify/verify_roll.py"))

    def test_acceptance_machinery_and_classifier(self):
        for p in ("tools/verify/acceptance.py", "tools/harness/pressure.py"):
            self.assertEqual(commands([p]), ["make test-acceptance"] + COVER + [ACCEPT], p)
        self.assertEqual(commands(["tools/verify/reach.py"]), ["make test-acceptance"])
        self.assertEqual(commands(["tools/verify/tests/test_reach.py"]), ["make test-acceptance"])

    def test_the_bus_gate_follows_the_bus(self):
        # a module of remix bus, and the gate itself
        self.assertIn(BUS, commands(["modules/send/send_client.asm"]))
        self.assertIn(BUS, commands(["tools/verify/verify_bus.py"]))
        self.assertNotIn(BUS, commands(["modules/character/engine.asm"]))

    def test_toolchain_and_port(self):
        self.assertEqual(commands(["tools/patches/dsp56300.patch"]), ["make ci-dsp", BUS] + COVER)
        self.assertEqual(commands(["tools/emu/ot_emu/machine.h"]), ["make ci-emu", "make emu-cf"] + REMIX)
        self.assertEqual(commands(["scripts/refhash.sh"]), ["scripts/refhash.sh check"])


class MakefileTests(unittest.TestCase):
    def test_unchanged_makefile_reaches_nothing(self):
        self.assertEqual(commands(["Makefile"]), [])
        self.assertIn("no target", note("Makefile"))

    def test_a_new_target_outside_the_check_graph_reaches_nothing(self):
        head = MAKE_BASE + "ghidra: ## import\n\tpython3 tools/ghidra/ot_ghidra.py\n"
        self.assertEqual(commands(["Makefile"], c=ctx(make_head=head)), [])
        self.assertIn("ghidra", note("Makefile", ctx(make_head=head)))

    def test_a_check_target_reaches_identity_the_cover_and_ci(self):
        head = MAKE_BASE.replace("\tpython3 tools/verify/verify_menu.py\n", "\tpython3 tools/verify/verify_menu.py\n\tpython3 tools/verify/verify_usb.py\n")
        self.assertEqual(commands(["Makefile"], c=ctx(make_head=head)), [IDENTITY] + COVER + ["make ci"])

    def test_a_variable_or_define_reaches_identity_and_the_cover(self):
        self.assertEqual(commands(["Makefile"], c=ctx(make_head=MAKE_BASE.replace("BUILD ?= 79", "BUILD ?= 80"))), [IDENTITY] + COVER + ["make ci"])
        self.assertEqual(commands(["Makefile"], c=ctx(make_head=MAKE_BASE.replace('@test -n "$(REMIX)"', "@true"))), [IDENTITY] + COVER + ["make ci"])

    def test_runner_and_ci_targets(self):
        head = MAKE_BASE.replace("\tpython3 tools/verify/acceptance.py\n", "\tpython3 tools/verify/acceptance.py --x\n")
        self.assertEqual(commands(["Makefile"], c=ctx(make_head=head)), ["make test-acceptance"])
        head = MAKE_BASE.replace("\tscripts/vendor.sh dsp56300\n", "\tscripts/vendor.sh dsp56300 mc68k\n")
        self.assertEqual(commands(["Makefile"], c=ctx(make_head=head)), ["make ci"])

    def test_comments_and_phony_are_not_changes(self):
        head = MAKE_BASE.replace("## the build", "## THE build").replace(".PHONY: bus\n", ".PHONY: bus cycles\n# a note\n")
        self.assertEqual(commands(["Makefile"], c=ctx(make_head=head)), [])

    def test_without_a_base_the_makefile_is_the_cover(self):
        self.assertEqual(commands(["Makefile"], c=ctx(make_base=None)), COVER + ["make ci"])


class PlanTests(unittest.TestCase):
    def test_docs_and_ci(self):
        self.assertEqual(commands(["docs/contributing/MODULES.md", "README.md"]), ["python3 tools/verify/verify_docs.py"])
        self.assertEqual(commands([".github/workflows/ci.yml"]), ["make ci"])

    def test_unclassified_reaches_the_cover_and_says_so(self):
        self.assertIn("unclassified: the cover (2 of 3 remixes)", note("mystery.bin"))
        self.assertEqual(commands(["mystery.bin"]), COVER)

    def test_all_makes_the_floor_every_remix(self):
        c = ctx(); c.floor = list(c.remixes)
        self.assertEqual(commands(["mystery.bin"], c=c), EVERY)
        self.assertEqual(note("mystery.bin", c), "unclassified: every remix")

    def test_the_cover_is_the_fewest_remixes_carrying_every_module(self):
        self.assertEqual(ctx().cover(), ["bamsep26", "miniverb"])
        c = ctx()
        c.remixes_of = {"A": ["x", "y"], "B": ["x"], "C": ["z"]}
        self.assertEqual(c.cover(), ["x", "z"])      # y is a subset of x
        c.remixes_of = {"A": ["x", "y"], "B": ["y"], "C": ["z"], "D": ["x"]}
        self.assertEqual(c.cover(), ["x", "y", "z"])  # B only in y, D only in x
        c.remixes_of = {"A": ["x"], "B": []}
        self.assertEqual(c.cover(), ["x"])           # a module no remix carries is not coverable

    def test_order_is_fixed_and_each_command_once(self):
        cmds = commands(["docs/x.md", "modules/character/a.asm", "tools/build/dsp_modmap.py", "modules/character/b.asm", "tools/verify/verify_menu.py"])
        self.assertEqual(cmds[0], "python3 tools/verify/verify_docs.py")
        self.assertEqual(len(cmds), len(set(cmds)))
        shared = [c for c in cmds if c.startswith("make check-shared")]
        self.assertEqual(shared, [SHARED_ALL])        # the cover's and CHARACTER's shared lines, merged
        self.assertLess(cmds.index("scripts/refhash.sh check"), cmds.index(IDENTITY))
        self.assertLess(cmds.index(IDENTITY), cmds.index(SHARED_ALL))
        self.assertLess(cmds.index(SHARED_ALL), cmds.index("make check-remix REMIX=bamsep26"))
        self.assertEqual(cmds.count("make check-remix REMIX=bamsep26"), 1)

    def test_halves_merge_into_one_shared_line(self):
        # a shared gate + a per-remix gate + one module's full check: one check-shared, one check-remix each
        cmds = commands(["tools/verify/verify_knob_clicks.py", "tools/verify/verify_menu.py", "modules/miniverb/a.asm"])
        self.assertEqual(cmds, COVER + ["make accept REMIX=miniverb STRESS_SOURCE=${STRESS_SOURCE}"])

    def test_manifest_display_fields_alone_reach_the_docs_gate(self):
        base = 'MODULE = Module(name="x", key="X", doc="old", proof=Proof.PORT, proof_note="n", params=(Param("A", doc="a"),))\n'
        head = base.replace('doc="old"', 'doc="new"').replace('proof=Proof.PORT', 'proof=Proof.HARDWARE').replace('doc="a"', 'doc="b"')
        self.assertTrue(reach.manifest_display_only(base, head))
        self.assertTrue(reach.manifest_display_only('"""a docstring"""\n' + base, '"""another"""\n' + head))
        self.assertFalse(reach.manifest_display_only(base, head.replace('key="X"', 'key="Y"')))
        self.assertFalse(reach.manifest_display_only(base, head + 'dear={"A": 1}\n'))
        self.assertFalse(reach.manifest_display_only(None, head))
        c = ctx()
        c.read_base = lambda p: base
        c.read = lambda p: head
        rows = reach.classify(["modules/character/manifest.py"], c)
        self.assertEqual([cmd for _, g, _ in rows for _, cmd in g], ["python3 tools/verify/verify_docs.py"])
        self.assertIn("display fields only", rows[0][2])
        c.read = lambda p: head.replace('key="X"', 'key="Y"')
        self.assertIn('make check-remix REMIX=bamsep26 MODULES="CHARACTER"', [cmd for _, g, _ in reach.classify(["modules/character/manifest.py"], c) for _, cmd in g])

    def test_remix_display_fields_alone_reach_the_docs_gate(self):
        base = 'REMIX = Remix(name="miniverb", doc="old", proof=Proof.PORT, proof_note="n", modules=("MINIVERB",))\n'
        head = base.replace('doc="old"', 'doc="new"').replace('proof_note="n"', 'proof_note="m"')
        c = ctx()
        c.read_base = lambda p: base
        c.read = lambda p: head
        rows = reach.classify(["remixes/miniverb/remix.py"], c)
        self.assertEqual([cmd for _, g, _ in rows for _, cmd in g], ["python3 tools/verify/verify_docs.py"])
        self.assertIn("display fields only", rows[0][2])
        c.read = lambda p: head.replace('("MINIVERB",)', '("MINIVERB", "SEND")')
        self.assertEqual([cmd for _, g, _ in reach.classify(["remixes/miniverb/remix.py"], c) for _, cmd in g],
                         ["make check REMIX=miniverb", "make accept REMIX=miniverb STRESS_SOURCE=${STRESS_SOURCE}"])

    def test_identity_extras_replan_into_the_accept_line_and_the_shards(self):
        queue = [("check-remix", "python3 tools/verify/check_shards.py --jobs 4 bamsep26 miniverb", ["p"]),
                 ("accept", 'make accept REMIXES="bamsep26 miniverb" STRESS_SOURCE=${STRESS_SOURCE} JOBS=4', ["p"])]
        extra = [reach.cmd_check("usb"), reach.cmd_accept("usb")]
        cmds = [c for _, c, _ in reach.replan(queue, extra, stress="/p", jobs=4)]
        self.assertEqual(cmds, ['make accept REMIXES="bamsep26 miniverb usb" STRESS_SOURCE=${STRESS_SOURCE} JOBS=4'])
        cmds = [c for _, c, _ in reach.replan([("check-remix", "make check-remix REMIX=bamsep26", ["p"])],
                                              [reach.cmd_check("usb")], stress=None, jobs=1)]
        self.assertEqual(cmds, ['make check-shared REMIXES="usb"', "make check-remix REMIX=bamsep26", "make check-remix REMIX=usb"])

    def test_a_stale_port_is_detected(self):
        import os, tempfile, time
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "src").mkdir(); (d / "src/machine.cpp").write_text("x")
            exe = d / "ot_emu"; exe.write_text("bin")
            old = time.time() - 100
            os.utime(d / "src/machine.cpp", (old, old))
            self.assertFalse(reach.port_is_stale(exe, d / "src"))
            os.utime(exe, (old - 100, old - 100))
            self.assertTrue(reach.port_is_stale(exe, d / "src"))
            # a missing binary is stale: without it the port gates SKIP
            self.assertTrue(reach.port_is_stale(d / "missing", d / "src"))

    def test_sharded_gives_the_accept_line_jobs(self):
        items = [("accept", 'make accept REMIXES="bamsep26 miniverb" STRESS_SOURCE=${STRESS_SOURCE}', ["p"]),
                 ("accept", "make accept REMIX=usb STRESS_SOURCE=${STRESS_SOURCE}", ["p"])]
        self.assertEqual([c for _, c, _ in reach.sharded(items, 4)],
                         ['make accept REMIXES="bamsep26 miniverb" STRESS_SOURCE=${STRESS_SOURCE} JOBS=4',
                          "make accept REMIX=usb STRESS_SOURCE=${STRESS_SOURCE}"])
        self.assertEqual(reach.unsharded(reach.sharded(items, 4)), items)

    def test_sharded_collapses_the_check_remix_lines(self):
        items = reach.plan(reach.classify(["tools/verify/verify_menu.py"], ctx()))
        cmds = [c for _, c, _ in reach.sharded(items, 4)]
        self.assertEqual(cmds, ["python3 tools/verify/check_shards.py --jobs 4 bamsep26 miniverb"])
        # one remix: its shared half, then its per-remix half split by gate
        one = reach.plan(reach.classify(["remixes/miniverb/remix.py"], ctx()), accept_runs_check=False)
        self.assertEqual([c for _, c, _ in reach.sharded(one, 4)],
                         ['make check-shared REMIXES="miniverb"', "python3 tools/verify/check_shards.py --jobs 4 miniverb",
                          "make accept REMIX=miniverb STRESS_SOURCE=${STRESS_SOURCE}"])

    def test_scoped_shared_lines_merge_and_an_unscoped_one_wins(self):
        self.assertEqual(reach.shared_modules('make check-shared REMIXES="a" MODULES="KITS,CC MAP"'), ["KITS", "CC MAP"])
        self.assertIsNone(reach.shared_modules('make check-shared REMIXES="a"'))
        cmds = commands(["modules/character/a.asm", "modules/send/b.asm"])
        self.assertIn('make check-shared REMIXES="bamsep26 usb" MODULES="CHARACTER,SEND"', cmds)
        cmds = commands(["modules/character/a.asm", "tools/verify/verify_knob_clicks.py"])
        self.assertEqual([c for c in cmds if c.startswith("make check-shared")], [SHARED_ALL])

    def test_an_unscoped_shared_line_stands_for_its_own_remixes_modules(self):
        # a tool change's floor (miniverb) beside a SEND change on bamsep26:
        # CHARACTER, which only bamsep26 carries and nothing reached, stays out
        rows = [("tools/x.py", [reach.cmd_check_shared(["miniverb"])], ""),
                ("modules/send/b.asm", [reach.cmd_check_shared(["bamsep26"], ["SEND"])], "")]
        cmds = [c for _, c, _ in reach.plan(rows, keys_of=ctx().keys_of)]
        self.assertEqual(cmds, ['make check-shared REMIXES="bamsep26 miniverb" MODULES="MINIVERB,SEND"'])
        # without the remixes' modules the unscoped line wins, as before
        cmds = [c for _, c, _ in reach.plan(rows)]
        self.assertEqual(cmds, ['make check-shared REMIXES="bamsep26 miniverb"'])

    def test_per_remix_lines_carry_their_modules_into_the_shards(self):
        rows = [("modules/send/a.asm", [reach.cmd_check_remix("bamsep26", ["SEND"])], ""),
                ("modules/character/b.asm", [reach.cmd_check_remix("bamsep26", ["CHARACTER"])], "")]
        self.assertEqual([c for _, c, _ in reach.plan(rows)],
                         ['make check-remix REMIX=bamsep26 MODULES="CHARACTER,SEND"'])
        rows.append(("tools/x.py", [reach.cmd_check_remix("bamsep26")], ""))
        self.assertEqual([c for _, c, _ in reach.plan(rows)], ["make check-remix REMIX=bamsep26"])
        items = reach.sharded([("check-remix", 'make check-remix REMIX=bamsep26 MODULES="CHARACTER,SEND"', ["p"]),
                               ("check-remix", 'make check-remix REMIX=usb MODULES="SEND"', ["p"])], 3)
        self.assertEqual(items[0][1], 'python3 tools/verify/check_shards.py --jobs 3 --modules "CHARACTER,SEND" bamsep26 usb')
        self.assertEqual(reach.shards_line(items[0][1]), (["bamsep26", "usb"], ["CHARACTER", "SEND"]))
        self.assertEqual([c for _, c, _ in reach.unsharded(items)],
                         ['make check-remix REMIX=bamsep26 MODULES="CHARACTER,SEND"',
                          'make check-remix REMIX=usb MODULES="CHARACTER,SEND"'])

    def test_a_variant_only_gate_is_a_gate_of_its_module(self):
        from remix import registry
        scripts = {g.script for g in reach.variant_gates(registry.modules()["USB"])}
        self.assertIn("tools/verify/verify_usb_post.py", scripts)
        self.assertIn("tools/verify/verify_usb_align.py", scripts)

    def test_selection_only_store_gate_reaches_its_actual_clients(self):
        context = reach.Context.from_registry()
        script = "tools/verify/verify_store_part_selection.py"
        self.assertEqual(context.gate_owners[script], ["STORE"])
        self.assertEqual(context.gate_remixes[script],
                         {"hooks-boot", "midi-follow", "midi-follow-events", "midi-loopback"})
        rows = reach.classify([script], context)
        self.assertEqual(reach.remixes_reached(rows),
                         ["hooks-boot", "midi-follow", "midi-follow-events", "midi-loopback"])

    def test_remixes_reached(self):
        rows = reach.classify(["modules/character/a.asm", "remixes/miniverb/remix.py"], ctx())
        self.assertEqual(reach.remixes_reached(rows), ["bamsep26", "miniverb", "usb"])
        rows = reach.classify(["tools/verify/verify_knob_clicks.py"], ctx())
        self.assertEqual(reach.remixes_reached(rows), ["bamsep26", "miniverb"])


class GraphTests(unittest.TestCase):
    def test_path_refs_count_runs_and_reads_not_prose(self):
        src = '''
"""tools/harness/prose.py is named in this docstring."""
import subprocess, sys
# tools/harness/comment.py
subprocess.run([sys.executable, "tools/harness/run_me.py", "--x"])
p = ROOT / "tools/hw/read_me.py"
print("see tools/harness/message.py")
sys.exit(f"run tools/harness/exit_msg.py first")
open("scripts/opened.sh")
'''
        self.assertEqual(reach.path_refs(src), {"tools/harness/run_me.py", "tools/hw/read_me.py", "scripts/opened.sh"})

    def test_resolve_import_by_toolpath_rules(self):
        known = {"tools/remix/__init__.py", "tools/remix/schema.py", "tools/harness/send_probe.py", "tools/hw/ot_bank.py"}
        ex = known.__contains__
        self.assertEqual(reach.resolve_import("remix", ["schema"], ex), {"tools/remix/__init__.py", "tools/remix/schema.py"})
        self.assertEqual(reach.resolve_import("remix.schema", ["Module"], ex), {"tools/remix/schema.py"})
        self.assertEqual(reach.resolve_import("send_probe", [], ex), {"tools/harness/send_probe.py"})
        self.assertEqual(reach.resolve_import("hw", ["ot_bank"], ex), {"tools/hw/ot_bank.py"})
        self.assertEqual(reach.resolve_import("json", [], ex), set())

    def test_makefile_targets_and_changes(self):
        t, v, d = reach.makefile_targets(MAKE_BASE)
        self.assertIn("verify-shared", t)
        self.assertEqual(v["BUILD"], "BUILD ?= 79")
        self.assertIn("need-remix", d)
        self.assertEqual(reach.makefile_changes(MAKE_BASE, MAKE_BASE), ([], []))
        self.assertEqual(reach.makefile_changes(MAKE_BASE, MAKE_BASE + "x: y\n\tz\n"), (["x"], []))
        self.assertEqual(reach.recipe_scripts(MAKE_BASE, "verify-remix"), {"tools/verify/verify_menu.py", "tools/verify/verify_set.py"})


if __name__ == "__main__":
    unittest.main()


class QuickTests(unittest.TestCase):
    """The quick tier: fewer remixes, no identity, no accept."""

    def quick(self):
        c = ctx()
        c.quick = True
        c.test_remixes = {"miniverb"}
        c.floor = [max(c.floor, key=lambda r: (c._modules_of().get(r, 0), r))]
        return c

    def test_a_module_checks_its_user_facing_carriers(self):
        c = self.quick()
        self.assertEqual(c.carriers(["bamsep26", "usb"]), ["bamsep26", "usb"])
        self.assertEqual(c.carriers(["miniverb"]), ["miniverb"])

    def test_only_test_carriers_check_the_smallest(self):
        c = self.quick()
        c.test_remixes = {"bamsep26", "usb", "miniverb"}
        self.assertEqual(len(c.carriers(["bamsep26", "usb"])), 1)

    def test_the_floor_is_one_remix_and_a_build_change_skips_identity(self):
        c = self.quick()
        self.assertEqual(len(c.floor), 1)
        kinds = [k for k, _ in c.build_change()]
        self.assertIn("refhash", kinds)
        self.assertNotIn("identity", kinds)

    def test_full_is_unchanged(self):
        c = ctx()
        self.assertEqual(c.carriers(["bamsep26", "usb"]), ["bamsep26", "usb"])
        self.assertIn("identity", [k for k, _ in c.build_change()])

    def test_a_makefile_check_target_skips_identity_when_quick(self):
        head = MAKE_BASE.replace("\tpython3 tools/verify/verify_menu.py", "\tpython3 tools/verify/verify_menu.py --x")
        c = ctx(make_head=head)
        c.quick = True
        kinds = [k for _, g, _ in reach.classify(["Makefile"], c) for k, _ in g]
        self.assertNotIn("identity", kinds)
        c.quick = False
        self.assertIn("identity", [k for _, g, _ in reach.classify(["Makefile"], c) for k, _ in g])


class TestRemixTests(unittest.TestCase):
    """remixes/test/ is left out unless TESTS=1."""

    def ctx_without_tests(self):
        c = ctx()
        c.include_tests = False
        c.test_remixes = {"miniverb"}
        c.test_carriers = {"MINIVERB": ["miniverb"]}
        c.remixes_of = {k: [r for r in v if r != "miniverb"] for k, v in c.remixes_of.items()}
        c.remixes = [r for r in c.remixes if r != "miniverb"]
        return c

    def test_a_module_only_in_test_remixes_is_not_checked(self):
        rows = reach.classify(["modules/miniverb/engine.asm"], self.ctx_without_tests())
        self.assertEqual([cmd for _, g, _ in rows for _, cmd in g], ["python3 tools/remix/selftest.py"])
        self.assertIn("carried only by test remixes", rows[0][2])

    def test_a_test_remix_edit_is_not_checked(self):
        rows = reach.classify(["remixes/test/miniverb/remix.py"], self.ctx_without_tests())
        kinds = [k for _, g, _ in rows for k, _ in g]
        self.assertNotIn("check", kinds)
        self.assertNotIn("accept", kinds)

    def test_identity_names_only_the_remixes_in_play(self):
        c = self.ctx_without_tests()
        self.assertIn("--remixes bamsep26 usb", c.identity()[1])
        self.assertNotIn("--remixes", ctx().identity()[1])


class PlanJsonTests(unittest.TestCase):
    def test_one_entry_per_command_in_plan_order(self):
        rows = reach.classify(["remixes/miniverb/remix.py"], ctx())
        items = reach.plan(rows)
        d = reach.plan_json("origin/main", "abc", True, 2, reach.remixes_reached(rows), items)
        self.assertEqual([g["command"] for g in d["gates"]], [c for _, c, _ in items])
        self.assertEqual(d["remixes"], ["miniverb"])
        self.assertEqual((d["tier"], d["jobs"], d["merge_base"]), ("quick", 2, "abc"))
        self.assertEqual(json.loads(json.dumps(d)), d)

    def test_a_full_plan_says_so_and_nothing_to_run_is_an_empty_list(self):
        d = reach.plan_json("origin/main", None, False, 1, [], [])
        self.assertEqual((d["tier"], d["gates"]), ("full", []))

    def test_main_prints_only_the_json_on_stdout(self):
        import contextlib
        import io
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = reach.main(["--json", "--paths", "docs/README.md"])
        self.assertEqual(rc, 0)
        d = json.loads(out.getvalue())
        self.assertEqual(d["tier"], "quick")
        self.assertIn("docs/README.md", err.getvalue())

    def items(self):
        return [("verify_docs", "python3 tools/verify/verify_docs.py", ["a"]),
                ("test-acceptance", "make test-acceptance", ["b"]),
                ("ci", "make ci", ["g"]),
                ("ci-dsp", "make ci-dsp", ["h"]),
                ("ci-emu", "make ci-emu", ["i"]),
                ("selftest", "python3 tools/remix/selftest.py", ["f"]),
                ("refhash", "scripts/refhash.sh check", ["c"]),
                ("check-shared", 'make check-shared REMIXES="x y"', ["d"]),
                ("check-remix", 'python3 tools/verify/check_shards.py --jobs 3 --modules "K1,K2" x y', ["e"])]

    def test_entries_group_the_quick_commands_and_split_the_shards_per_remix(self):
        got = {e["name"]: [c for _, c, _ in e["items"]] for e in reach.entries(self.items(), 3)}
        self.assertEqual(list(got), ["refhash", "check-shared", "check-shared (module gates)",
                                     "check-remix x", "check-remix y", "selftest"])
        self.assertEqual(got["selftest"], ["python3 tools/remix/selftest.py"])
        commands = [c for cs in got.values() for c in cs]
        for dedicated in ("verify_docs.py", "make test-acceptance", "make ci", "make ci-dsp", "make ci-emu"):
            self.assertFalse([c for c in commands if dedicated in c], dedicated)
        self.assertEqual(got["check-shared"], ['make check-shared REMIXES="x y" SHARED_PART=rest'])
        self.assertEqual(got["check-shared (module gates)"], ['make check-shared REMIXES="x y" SHARED_PART=modules'])
        self.assertEqual(got["check-remix y"],
                         ['python3 tools/verify/check_shards.py --jobs 3 --modules "K1,K2" y'])

    def test_a_split_remix_is_units_that_cover_every_gate_job_once(self):
        items = [("check-remix", "python3 tools/verify/check_shards.py --jobs 3 --modules \"K1\" x octabam", ["e"])]
        parts = {"long": ("remix-switch",), "project": ("set", "plocks-p2")}
        with mock.patch.dict(reach.SPLIT_REMIX_JOBS, {"octabam": parts}):
            got = {e["name"]: e["items"][0][1] for e in reach.entries(items, 3)}
        pre = 'python3 tools/verify/check_shards.py --jobs 3 --modules "K1" '
        self.assertEqual(got["check-remix x"], pre + "x")
        self.assertEqual(got["check-remix octabam"], pre + "--skip-jobs remix-switch,set,plocks-p2 octabam")
        self.assertEqual(got["check-remix octabam (long)"], pre + "--only-jobs remix-switch octabam")
        self.assertEqual(got["check-remix octabam (project)"], pre + "--only-jobs set,plocks-p2 octabam")
        for line in got.values():
            self.assertEqual(reach.shards_line(line)[0], [line.split()[-1]])

    def test_the_brain_unit_exists_only_when_brain_is_reached(self):
        def names(modules):
            flag = f'--modules "{modules}" ' if modules else ""
            items = [("check-remix", f"python3 tools/verify/check_shards.py --jobs 3 {flag}octabam", ["e"])]
            return {e["name"]: e["items"][0][1] for e in reach.entries(items, 3)}
        got = names("BRAIN,KITS")
        self.assertEqual(got["check-remix octabam (brain)"], ".venv/bin/python3 tools/verify/verify_brain.py octabam")
        self.assertIn("check-remix octabam (brain)", names(""))              # an unscoped run reaches BRAIN too
        self.assertNotIn("check-remix octabam (brain)", names("KITS"))
        # additive: the plain unit still skips only the SPLIT_REMIX_JOBS parts, image stays in it
        self.assertNotIn("image", got["check-remix octabam"].split("--skip-jobs ")[1].split()[0].split(","))

    def test_recipe_scripts_follow_an_implementation_cut_into_halves(self):
        mk = ("verify-shared: ## x\n\t$(MAKE) -j1 verify-shared-impl\n\n"
              "verify-shared-impl: verify-shared-rest-impl $(if $(Y),,verify-shared-modules-impl)\n\n"
              "verify-shared-rest-impl:\n\tpython3 tools/a.py\n\n"
              "verify-shared-modules-impl:\n\tpython3 tools/b.py\n")
        self.assertEqual(reach.recipe_scripts(mk, "verify-shared"), {"tools/a.py", "tools/b.py"})

    def test_entries_name_a_lone_check_and_make_repeated_names_unique(self):
        items = [("check", "make check REMIX=x", []), ("check", "make check REMIX=x", []),
                 ("accept", 'make accept REMIXES="x y"', [])]
        self.assertEqual([e["name"] for e in reach.entries(items, 1)], ["check x", "check x #2", "accept"])

    def test_the_json_matrix_lists_each_units_commands(self):
        d = reach.plan_json("origin/main", None, True, 3, ["x", "y"], self.items())
        self.assertEqual([e["name"] for e in d["matrix"]][-1], "selftest")
        self.assertEqual(len(d["gates"]), 9)

    def test_only_keeps_one_unit_and_refuses_an_unknown_one(self):
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = reach.main(["--paths", "scripts/refhash.sh", "--only", "refhash"])
        self.assertEqual(rc, 0)
        self.assertIn("refhash.sh check", out.getvalue())
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), \
                self.assertRaises(SystemExit) as e:
            reach.main(["--paths", "scripts/refhash.sh", "--only", "nope"])
        self.assertIn("no such unit", str(e.exception))

    def test_json_refuses_run(self):
        import contextlib
        import io
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            reach.main(["--json", "--run"])


class VendorWriterTests(unittest.TestCase):
    """`reach --run` in a worktree must not run a step that writes the shared vendor/."""

    def test_a_shared_vendor_runs_the_tree_build_for_ci_emu_and_leaves_ci_dsp_and_ci_to_ci(self):
        cmd, note = reach.vendor_safe("ci-emu", "make ci-emu", True)
        self.assertEqual(cmd, "make ci-emu-tree")
        self.assertIn("scripts/vendor.sh", note)
        for kind in ("ci-dsp", "ci"):
            cmd, note = reach.vendor_safe(kind, f"make {kind}", True)
            self.assertIsNone(cmd)
            self.assertIn("left to CI", note)

    def test_an_own_vendor_or_another_step_is_unchanged(self):
        self.assertEqual(reach.vendor_safe("ci-dsp", "make ci-dsp", False), ("make ci-dsp", None))
        self.assertEqual(reach.vendor_safe("check-shared", 'make check-shared REMIXES="a"', True),
                         ('make check-shared REMIXES="a"', None))

    def test_a_symlinked_vendor_is_shared(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "real").mkdir()
            os.symlink(d / "real", d / "vendor")
            self.assertTrue(reach.shared_vendor(d))
            (d / "own").mkdir()
            (d / "own" / "vendor").mkdir()
            self.assertFalse(reach.shared_vendor(d / "own"))
