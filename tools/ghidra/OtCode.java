// Writes out/ghidra/code_runs.tsv: the address runs of consecutive instructions Ghidra's analysis found in
// MAIN_OS, "start<TAB>end" in hex, end exclusive, one run a line. Addresses only, no bytes.
// analyzeHeadless's -postScript; tools/build/cf_forms.py reads the committed copy
// (tools/build/cf_code_runs.tsv) to decode stock instructions without decoding the image's tables as code.
// OT_EXPORT_DIR names the directory (default out/ghidra). Programs other than MAIN_OS are skipped.
//@category octabam
import java.io.File;
import java.io.PrintWriter;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;

public class OtCode extends GhidraScript {

	@Override
	public void run() throws Exception {
		if (!currentProgram.getName().startsWith("MAIN_OS")) {
			println("OtCode: " + currentProgram.getName() + " skipped (stock ColdFire only)");
			return;
		}
		String dir = System.getenv("OT_EXPORT_DIR");
		File out = new File(dir == null || dir.isEmpty() ? "out/ghidra" : dir);
		out.mkdirs();
		long start = -1, end = -1, bytes = 0;
		int instructions = 0, runs = 0;
		try (PrintWriter w = new PrintWriter(new File(out, "code_runs.tsv"))) {
			InstructionIterator it = currentProgram.getListing().getInstructions(true);
			while (it.hasNext()) {
				Instruction i = it.next();
				long a = i.getAddress().getOffset();
				if (a != end) {
					if (start >= 0) {
						w.printf("%x\t%x%n", start, end);
						runs++;
					}
					start = a;
				}
				end = a + i.getLength();
				bytes += i.getLength();
				instructions++;
			}
			if (start >= 0) {
				w.printf("%x\t%x%n", start, end);
				runs++;
			}
		}
		println(String.format("OtCode: %d instructions in %d runs, %d bytes", instructions, runs, bytes));
	}
}
