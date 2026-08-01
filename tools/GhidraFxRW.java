//@category Octatrack
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.listing.*;
public class GhidraFxRW extends GhidraScript {
  void probe(long base, int n, String label) throws Exception {
    AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
    ReferenceManager rm = currentProgram.getReferenceManager();
    FunctionManager fm = currentProgram.getFunctionManager();
    println("\n===== " + label + " 0x" + Long.toHexString(base) + " .. +" + n + " =====");
    int reads = 0, writes = 0, other = 0;
    for (int k = 0; k < n; k++) {
      Address a = sp.getAddress(base + k);
      for (Reference r : rm.getReferencesTo(a)) {
        RefType t = r.getReferenceType();
        Function f = fm.getFunctionContaining(r.getFromAddress());
        String fn = f == null ? "(none)" : f.getName();
        if (t.isRead()) reads++; else if (t.isWrite()) writes++; else other++;
        println(String.format("  +%d  %-18s %-8s from %s @ %s", k, a, t.getName(),
                fn, r.getFromAddress()));
      }
    }
    println(String.format("  TOTAL: %d read, %d write, %d other", reads, writes, other));
  }
  public void run() throws Exception {
    probe(0x80000ec4L, 8, "FX1 effect id array");
    probe(0x80000eccL, 8, "FX2 effect id array");
  }
}
