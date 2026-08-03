//@category Octatrack
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.util.task.ConsoleTaskMonitor;

public class GhidraStageFunc extends GhidraScript {
  public void run() throws Exception {
    AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
    FunctionManager fm = currentProgram.getFunctionManager();
    DecompInterface dec = new DecompInterface();
    dec.openProgram(currentProgram);
    ConsoleTaskMonitor mon = new ConsoleTaskMonitor();
    long t = 0x400326d4L;
    Address a = sp.getAddress(t);
    Function f = fm.getFunctionContaining(a);
    if (f == null) { disassemble(a); f = createFunction(a, null); }
    DecompileResults r = dec.decompileFunction(f, 240, mon);
    println("\n===== 0x" + Long.toHexString(t) + " in " + f.getName() +
            " @ " + f.getEntryPoint() + " =====");
    println(r != null && r.decompileCompleted() ? r.getDecompiledFunction().getC() : "(failed)");
  }
}
