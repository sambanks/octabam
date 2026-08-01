//@category Octatrack
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.util.task.ConsoleTaskMonitor;
public class GhidraFxResolve extends GhidraScript {
  public void run() throws Exception {
    AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
    FunctionManager fm = currentProgram.getFunctionManager();
    DecompInterface dec = new DecompInterface(); dec.openProgram(currentProgram);
    ConsoleTaskMonitor mon = new ConsoleTaskMonitor();
    long[] t = {0x40031da4L, 0x4003bf64L};
    for (long s : t) {
      Address a = sp.getAddress(s);
      Function f = fm.getFunctionContaining(a);
      if (f == null) { disassemble(a); f = createFunction(a, null); }
      if (f == null) { println("[!] none @ "+Long.toHexString(s)); continue; }
      DecompileResults r = dec.decompileFunction(f, 180, mon);
      println("\n===== "+f.getName()+" @ "+f.getEntryPoint()+" =====");
      println(r!=null&&r.decompileCompleted()? r.getDecompiledFunction().getC() : "(failed)");
    }
  }
}
