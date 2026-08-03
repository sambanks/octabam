//@category Octatrack
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.util.task.ConsoleTaskMonitor;

public class GhidraRenderFunc extends GhidraScript {
  public void run() throws Exception {
    AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
    FunctionManager fm = currentProgram.getFunctionManager();
    DecompInterface dec = new DecompInterface();
    dec.openProgram(currentProgram);
    ConsoleTaskMonitor mon = new ConsoleTaskMonitor();
    long t = 0x40037590L;
    Address a = sp.getAddress(t);
    Function f = fm.getFunctionContaining(a);
    if (f == null) { disassemble(a); f = createFunction(a, null); }
    DecompileResults r = dec.decompileFunction(f, 180, mon);
    println("\n===== 0x" + Long.toHexString(t) + " in " + f.getName() +
            " @ " + f.getEntryPoint() + " =====");
    println(r != null && r.decompileCompleted() ? r.getDecompiledFunction().getC() : "(failed)");
  }
}
