//@category Octatrack
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;

public class GhidraDisasmAt extends GhidraScript {
  public void run() throws Exception {
    AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
    Listing listing = currentProgram.getListing();
    long[] targets = {0x40059a40, 0x40052494, 0x4005249a, 0x400524c6, 0x40052514,
                       0x400375f2, 0x40037608};
    for (long t : targets) {
      Address a = sp.getAddress(t);
      Instruction ins = listing.getInstructionAt(a);
      if (ins == null) { println("0x" + Long.toHexString(t) + ": no instruction at exact addr"); continue; }
      StringBuilder sb = new StringBuilder();
      sb.append("0x").append(Long.toHexString(t)).append("  len=").append(ins.getLength())
        .append("  ").append(ins.toString()).append("   bytes=");
      byte[] b = ins.getBytes();
      for (byte x : b) sb.append(String.format("%02x", x));
      println(sb.toString());
    }
  }
}
