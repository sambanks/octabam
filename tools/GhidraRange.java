//@category Octatrack
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
public class GhidraRange extends GhidraScript {
  public void run() throws Exception {
    AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
    Listing l = currentProgram.getListing();
    long a = 0x40059a40L, end = 0x40059ab0L;
    while (a < end) {
      Address ad = sp.getAddress(a);
      Instruction ins = l.getInstructionAt(ad);
      if (ins == null) { a += 2; continue; }
      StringBuilder b = new StringBuilder();
      for (byte x : ins.getBytes()) b.append(String.format("%02x", x));
      println("0x" + Long.toHexString(a) + "  " + b + "   " + ins.toString());
      a += ins.getLength();
    }
  }
}
