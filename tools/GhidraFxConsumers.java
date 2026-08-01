//@category Octatrack
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.util.task.ConsoleTaskMonitor;
import java.util.*;
public class GhidraFxConsumers extends GhidraScript {
  public void run() throws Exception {
    AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
    FunctionManager fm = currentProgram.getFunctionManager();
    DecompInterface dec = new DecompInterface(); dec.openProgram(currentProgram);
    ConsoleTaskMonitor mon = new ConsoleTaskMonitor();
    long[] sites = {0x40094014L, 0x400941c6L, 0x40096c16L, 0x40004c24L, 0x40043d28L};
    Set<Long> seen = new HashSet<>();
    for (long s : sites) {
      Address a = sp.getAddress(s);
      Function f = fm.getFunctionContaining(a);
      if (f == null) { println("[!] no function containing 0x"+Long.toHexString(s)); continue; }
      if (!seen.add(f.getEntryPoint().getOffset())) { println("(0x"+Long.toHexString(s)+" is inside "+f.getName()+", already shown)"); continue; }
      DecompileResults r = dec.decompileFunction(f, 180, mon);
      println("\n===== site 0x"+Long.toHexString(s)+" in "+f.getName()+" @ "+f.getEntryPoint()
              +" ("+f.getBody().getNumAddresses()+" B) =====");
      println(r!=null&&r.decompileCompleted()? r.getDecompiledFunction().getC() : "(decompile failed)");
    }
  }
}
