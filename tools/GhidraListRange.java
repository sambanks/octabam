//@category Octatrack
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
public class GhidraListRange extends GhidraScript {
  public void run() throws Exception {
    AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
    Listing l = currentProgram.getListing();
    long[][] r = {{0x40009360L,0x400093d0L},{0x4000937aL,0x400093a0L}};
    for (long[] q : r) {
      println("\n===== 0x"+Long.toHexString(q[0])+" .. 0x"+Long.toHexString(q[1])+" =====");
      InstructionIterator it = l.getInstructions(sp.getAddress(q[0]), true);
      while (it.hasNext()) {
        Instruction i = it.next();
        if (i.getAddress().getOffset() > q[1]) break;
        println(String.format("  %08x  %-28s %s", i.getAddress().getOffset(),
                i.toString(), i.getMnemonicString()));
      }
    }
  }
}
