//@category Octatrack
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.util.task.ConsoleTaskMonitor;
import java.util.*;
public class GhidraDelay extends GhidraScript {
  public void run() throws Exception {
    AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
    FunctionManager fm = currentProgram.getFunctionManager();
    DecompInterface dec = new DecompInterface(); dec.openProgram(currentProgram);
    ConsoleTaskMonitor mon = new ConsoleTaskMonitor();
    // sites that reference the FILTER / DELAY / PLATE descriptors directly,
    // i.e. outside the id-indexed tables
    long[] sites = {0x40005832L, 0x4008ce1cL, 0x4008cd34L};
    Set<Long> seen = new HashSet<>();
    for (long s : sites) {
      Address a = sp.getAddress(s);
      Function f = fm.getFunctionContaining(a);
      if (f == null) { println("[!] no function containing 0x"+Long.toHexString(s)); continue; }
      if (!seen.add(f.getEntryPoint().getOffset())) { println("(0x"+Long.toHexString(s)+" already shown)"); continue; }
      DecompileResults r = dec.decompileFunction(f, 180, mon);
      println("\n===== site 0x"+Long.toHexString(s)+" in "+f.getName()+" @ "+f.getEntryPoint()+" =====");
      println(r!=null&&r.decompileCompleted()? r.getDecompiledFunction().getC() : "(decompile failed)");
    }
  }
}
