// Headless post-script: decompile selected functions instead of the whole binary.
// @category HermesCTF
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.FunctionManager;
import java.io.File;
import java.io.PrintWriter;
import java.util.LinkedHashSet;
import java.util.Set;

public class ExportDecompile extends GhidraScript {
    private static final int DEFAULT_FUNCTION_LIMIT = 20;
    private static final int DECOMPILE_TIMEOUT_SECONDS = 20;

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 1) {
            throw new IllegalArgumentException(
                "usage: ExportDecompile.java OUTPUT [FUNCTION_OR_ADDRESS ... | --all]"
            );
        }

        FunctionManager manager = currentProgram.getFunctionManager();
        Set<Function> selected = selectFunctions(args, manager);
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        try (PrintWriter output = new PrintWriter(new File(args[0]), "UTF-8")) {
            output.println("/* selected functions: " + selected.size() + " */");
            for (Function function : selected) {
                if (monitor.isCancelled()) break;
                DecompileResults result = decompiler.decompileFunction(
                    function, DECOMPILE_TIMEOUT_SECONDS, monitor
                );
                output.println("/* " + function.getName() + " @ " + function.getEntryPoint() + " */");
                if (result.decompileCompleted()) output.println(result.getDecompiledFunction().getC());
                else output.println("/* decompilation failed */");
            }
        } finally {
            decompiler.dispose();
        }
    }

    private Set<Function> selectFunctions(String[] args, FunctionManager manager) {
        Set<Function> selected = new LinkedHashSet<>();
        if (args.length > 1 && "--all".equals(args[1])) {
            FunctionIterator functions = manager.getFunctions(true);
            while (functions.hasNext()) selected.add(functions.next());
            return selected;
        }

        for (int index = 1; index < args.length; index++) {
            Function function = resolve(args[index], manager);
            if (function != null) selected.add(function);
            else println("Function not found: " + args[index]);
        }
        if (!selected.isEmpty()) return selected;

        String[] preferred = {"main", "WinMain", "wWinMain", "_start", "entry"};
        for (String name : preferred) {
            Function function = resolve(name, manager);
            if (function != null) selected.add(function);
        }
        if (!selected.isEmpty()) return selected;

        FunctionIterator functions = manager.getFunctions(true);
        while (functions.hasNext() && selected.size() < DEFAULT_FUNCTION_LIMIT) {
            Function function = functions.next();
            if (!function.isThunk()) selected.add(function);
        }
        return selected;
    }

    private Function resolve(String selector, FunctionManager manager) {
        try {
            Address address = toAddr(selector);
            Function function = manager.getFunctionAt(address);
            return function != null ? function : manager.getFunctionContaining(address);
        } catch (RuntimeException ignored) {
            // Not an address; resolve it as a function name below.
        }
        FunctionIterator functions = manager.getFunctions(true);
        while (functions.hasNext()) {
            Function function = functions.next();
            if (selector.equals(function.getName())) return function;
        }
        return null;
    }
}
