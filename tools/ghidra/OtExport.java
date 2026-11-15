// Writes out/ghidra/symbols.tsv (space, address, size, name) and xrefs.tsv (space, from, to, kind) for the
// program's functions and the references to them. analyzeHeadless's -postScript; tools/build/symdb.py --ghidra
// reads the files. Space is "cf" for MAIN_OS; the DSP programs are skipped.
//@category octabam
import java.io.File;
import java.io.PrintWriter;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

public class OtExport extends GhidraScript {

	@Override
	public void run() throws Exception {
		if (!currentProgram.getName().startsWith("MAIN_OS") && !currentProgram.getName().startsWith("REMIX")) {
			println("OtExport: " + currentProgram.getName() + " skipped (ColdFire only)");
			return;
		}
		String dir = System.getenv("OT_EXPORT_DIR");
		File out = new File(dir == null || dir.isEmpty() ? "out/ghidra" : dir);
		out.mkdirs();
		int nf = 0, nx = 0;
		try (PrintWriter sy = new PrintWriter(new File(out, "symbols.tsv"));
			PrintWriter xr = new PrintWriter(new File(out, "xrefs.tsv"))) {
			FunctionIterator it = currentProgram.getFunctionManager().getFunctions(true);
			while (it.hasNext()) {
				Function f = it.next();
				sy.printf("cf\t%x\t%x\t%s%n", f.getEntryPoint().getOffset(), f.getBody().getNumAddresses(), f.getName());
				nf++;
				ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(f.getEntryPoint());
				while (refs.hasNext()) {
					Reference r = refs.next();
					String kind = r.getReferenceType().isCall() ? "call" : r.getReferenceType().isJump() ? "jump"
						: r.getReferenceType().isWrite() ? "write" : "read";
					xr.printf("cf\t%x\t%x\t%s%n", r.getFromAddress().getOffset(), f.getEntryPoint().getOffset(), kind);
					nx++;
				}
			}
		}
		println(String.format("OtExport: %d functions, %d references to them", nf, nx));
	}
}
