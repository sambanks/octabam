//@category Octatrack
// Trace how an FX slot's effect id becomes DSP behaviour.
//
// Question: the effect id is stored per-Part at +0x8ed80 (FX1) / +0x8ed88 (FX2)
// and indexes a per-slot table to reach a parameter descriptor (see
// PARAM_PAGES.md). What we do NOT know is whether that id also selects the
// ALGORITHM on the DSP56300, and whether the FX1 and FX2 slots are symmetric on
// the DSP side. That decides two things:
//   - whether the FX1 delay/reverb experiment can work at all;
//   - whether an unused effect id could host a new descriptor over an existing
//     algorithm (a "variant" effect) without any DSP work.
//
// This prints (1) every function that touches either id field, (2) the C for the
// audio-path and FX-page functions, so the id can be followed to the point where
// it reaches the voice buffer / DSP frame.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.scalar.Scalar;
import ghidra.util.task.ConsoleTaskMonitor;
import java.util.*;

public class GhidraFxTrace extends GhidraScript {
  DecompInterface dec;
  ConsoleTaskMonitor mon;
  FunctionManager fm;
  AddressSpace sp;
  Set<Long> done = new HashSet<>();

  // the two per-Part effect-id fields, as struct offsets used in `adda.l #imm`
  static final long FX1_OFF = 0x8ed80L, FX2_OFF = 0x8ed88L;

  static final long[] TARGETS = {
      0x40009094L,  // apply_part  -- writes the voice buffer; touches FX1 id @0x40009380
      0x4000c8a4L,  // frame builder -- assembles the DSP parameter frame
      0x40032814L,  // FX page class A (FILTER SPAT DEL EQ PHSR FLNG CHOR COMB)
      0x400328e4L,  // FX page class B (DJEQ PLTE SPRG DARK COMP MBC LOFI)
      0x400326d4L,  // called with the resolved descriptor pointer
      0x40031ee0L,  // param definition lookup (min@0x6a max@0x9a)
  };

  Function force(long s) throws Exception {
    Address a = sp.getAddress(s);
    Function f = fm.getFunctionContaining(a);
    if (f == null) {
      disassemble(a);
      f = createFunction(a, null);
    }
    return f;
  }

  void dump(long s, String label) throws Exception {
    Function f = force(s);
    if (f == null) { println("[!] no function @ " + Long.toHexString(s)); return; }
    if (!done.add(f.getEntryPoint().getOffset())) return;
    DecompileResults r = dec.decompileFunction(f, 180, mon);
    println("\n=============== " + label + "  " + f.getName() + " @ " + f.getEntryPoint()
            + "  (" + f.getBody().getNumAddresses() + " bytes) ===============");
    println(r != null && r.decompileCompleted()
            ? r.getDecompiledFunction().getC()
            : "  (decompile failed: " + (r != null ? r.getErrorMessage() : "null") + ")");
  }

  // Scalar sweep: find every instruction with 0x8ed80 / 0x8ed88 as an immediate,
  // and report the containing function. (A reference sweep would miss these --
  // they are struct offsets in `adda.l #imm,aN`, not addresses.)
  void sites() throws Exception {
    println("=============== functions touching the FX id fields ===============");
    Map<String, List<String>> byFunc = new TreeMap<>();
    InstructionIterator it = currentProgram.getListing().getInstructions(true);
    while (it.hasNext()) {
      Instruction ins = it.next();
      for (int i = 0; i < ins.getNumOperands(); i++) {
        Object[] ops = ins.getOpObjects(i);
        for (Object o : ops) {
          if (!(o instanceof Scalar)) continue;
          long v = ((Scalar) o).getUnsignedValue();
          if (v != FX1_OFF && v != FX2_OFF) continue;
          Function f = fm.getFunctionContaining(ins.getAddress());
          String key = f == null ? "(no function)"
                     : f.getName() + " @ " + f.getEntryPoint();
          byFunc.computeIfAbsent(key, k -> new ArrayList<>())
                .add((v == FX1_OFF ? "FX1" : "FX2") + " @" + ins.getAddress());
        }
      }
    }
    for (Map.Entry<String, List<String>> e : byFunc.entrySet()) {
      int fx1 = 0, fx2 = 0;
      for (String s : e.getValue()) { if (s.startsWith("FX1")) fx1++; else fx2++; }
      println(String.format("  %-44s FX1x%-3d FX2x%-3d", e.getKey(), fx1, fx2));
    }
    println("  (" + byFunc.size() + " functions)\n");
    println("NOTE: a function reading FX1 but not FX2 may still handle both --");
    println("0x8ed88 = 0x8ed80 + 8, so one base load can serve both fields.\n");
  }

  public void run() throws Exception {
    sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
    fm = currentProgram.getFunctionManager();
    dec = new DecompInterface();
    dec.openProgram(currentProgram);
    mon = new ConsoleTaskMonitor();

    sites();
    String[] labels = {"apply_part", "frame_builder", "fx_page_class_A",
                       "fx_page_class_B", "descriptor_consumer", "param_def"};
    for (int i = 0; i < TARGETS.length; i++) dump(TARGETS[i], labels[i]);
    println("\n[GhidraFxTrace] done.");
  }
}
