//@category Octatrack
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.listing.*;
import java.util.*;

public class GhidraListXrefs extends GhidraScript {
  public void run() throws Exception {
    AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
    long[] targets = {0x400d6090L, 0x400d5fdcL, 0x400d6150L};
    ReferenceManager rm = currentProgram.getReferenceManager();
    FunctionManager fm = currentProgram.getFunctionManager();
    for (long t : targets) {
      Address a = sp.getAddress(t);
      println("\n===== xrefs TO 0x" + Long.toHexString(t) + " =====");
      ReferenceIterator it = rm.getReferencesTo(a);
      int n = 0;
      while (it.hasNext()) {
        Reference r = it.next();
        Address from = r.getFromAddress();
        Function f = fm.getFunctionContaining(from);
        println("  from 0x" + from + "  in " + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?") +
                "  type=" + r.getReferenceType());
        n++;
      }
      println("  (" + n + " references)");
    }
  }
}
