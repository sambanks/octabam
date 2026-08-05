//@category Octatrack
// Find a contiguous run of RAM that no code references, for the FX2 chooser's
// runtime list buffer (BUS.md stage-2 selector). GhidraRamFree.java asked the
// same question about one hardcoded range; this sweeps and reports every gap,
// so the choice is made from data rather than from a claim in NOTES.md.
//
// LIMIT, stated plainly: this proves no *statically recoverable* reference.
// Code that computes an address at runtime (base + index, jump tables) would
// not show up. It narrows the field; it is not proof the RAM is unused.
import ghidra.app.script.GhidraScript;

public class GhidraRamScan extends GhidraScript {
  public void run() throws Exception {
    var sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
    var rm = currentProgram.getReferenceManager();
    var fm = currentProgram.getFunctionManager();

    long lo = 0x80006000L, hi = 0x80008000L;
    int want = 64;                       // bytes we need, with margin over the 20 required

    println(String.format("=== reference sweep 0x%08x..0x%08x ===", lo, hi));
    long runStart = -1;
    long bestStart = -1, bestLen = 0;
    for (long a = lo; a < hi; a += 4) {
      var ri = rm.getReferencesTo(sp.getAddress(a));
      int n = 0;
      StringBuilder who = new StringBuilder();
      while (ri.hasNext()) {
        var r = ri.next(); n++;
        if (n <= 3) {
          var f = fm.getFunctionContaining(r.getFromAddress());
          who.append(" ").append(f != null ? f.getName() : "?")
             .append(r.getReferenceType().isWrite() ? "(W)" : "");
        }
      }
      if (n > 0) {
        println(String.format("  used 0x%08x refs=%-3d%s", a, n, who));
        if (runStart >= 0 && a - runStart > bestLen) { bestLen = a - runStart; bestStart = runStart; }
        runStart = -1;
      } else if (runStart < 0) {
        runStart = a;
      }
    }
    if (runStart >= 0 && hi - runStart > bestLen) { bestLen = hi - runStart; bestStart = runStart; }

    println(String.format("%n  longest unreferenced run: 0x%08x, %d bytes (need %d)",
                          bestStart, bestLen, want));
  }
}
