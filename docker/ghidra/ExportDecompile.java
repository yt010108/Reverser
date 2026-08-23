// Headless Ghidra post-script: exports decompiled C for every function.
// @category HermesCTF
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import java.io.File;
import java.io.PrintWriter;

public class ExportDecompile extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) throw new IllegalArgumentException("output path required");
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        try (PrintWriter output = new PrintWriter(new File(args[0]), "UTF-8")) {
            FunctionIterator functions = currentProgram.getFunctionManager().getFunctions(true);
            for (Function function : functions) {
                if (monitor.isCancelled()) break;
                DecompileResults result = decompiler.decompileFunction(function, 60, monitor);
                output.println("/* " + function.getName() + " @ " + function.getEntryPoint() + " */");
                if (result.decompileCompleted()) output.println(result.getDecompiledFunction().getC());
                else output.println("/* decompilation failed */");
            }
        } finally {
            decompiler.dispose();
        }
    }
}
