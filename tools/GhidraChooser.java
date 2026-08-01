//@category Octatrack
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.util.task.ConsoleTaskMonitor;
import java.util.*;
public class GhidraChooser extends GhidraScript {
  public void run() throws Exception {
    AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
    FunctionManager fm = currentProgram.getFunctionManager();
    DecompInterface dec = new DecompInterface(); dec.openProgram(currentProgram);
    ConsoleTaskMonitor mon = new ConsoleTaskMonitor();
    long[] sites = {0x40052496L, 0x40059a42L, 0x400375f4L};
    Set<Long> seen = new HashSet<>();
    for (long s : sites) {
      Address a = sp.getAddress(s);
      Function f = fm.getFunctionContaining(a);
      if (f == null) { disassemble(a); f = createFunction(a, null); }
      if (f == null) { println("[!] none @ "+Long.toHexString(s)); continue; }
      if (!seen.add(f.getEntryPoint().getOffset())) continue;
      DecompileResults r = dec.decompileFunction(f, 180, mon);
      println("\n===== site 0x"+Long.toHexString(s)+" in "+f.getName()+" @ "+f.getEntryPoint()+" =====");
      println(r!=null&&r.decompileCompleted()? r.getDecompiledFunction().getC() : "(failed)");
    }
  }
}
