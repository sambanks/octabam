//@category Octatrack
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;

public class GhidraInstrAt extends GhidraScript {
  public void run() throws Exception {
    AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
    Listing listing = currentProgram.getListing();
    long[] targets = {0x400375ee, 0x400375f0, 0x400375f2, 0x400375f4,
                       0x40037600, 0x40037604, 0x40037606, 0x40037608, 0x4003760a, 0x4003760c};
    for (long t : targets) {
      Address a = sp.getAddress(t);
      Instruction ins = listing.getInstructionContaining(a);
      if (ins == null) { println("0x" + Long.toHexString(t) + ": no instruction"); continue; }
      println("0x" + Long.toHexString(t) + "  ins@" + ins.getAddress() + " len=" + ins.getLength() +
              "  " + ins.toString());
    }
  }
}
