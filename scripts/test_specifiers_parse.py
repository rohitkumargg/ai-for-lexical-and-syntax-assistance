import sys, os
sys.path.insert(0, os.getcwd())
from test_parser import parse_source, get_first_error_object

code = """
extern int global_counter;
static const int MAX_LIMIT = 256;
volatile static int hardware_flag = 0;

static int process_buffer(const int id, volatile int *status_reg) {
    const char *label = "packet";
    static int local_acc = 0;
    local_acc += id;
    *status_reg = 1;
    return local_acc;
}
"""
tree, listeners, parser = parse_source(code, "specifier_test.c")
err = get_first_error_object(listeners)
print("Parse Error Object:", err)
print("ANTLR Syntax Errors Count:", parser.getNumberOfSyntaxErrors())
print("Parsed Program AST String:", tree.toStringTree(recog=parser)[:180] + " ...")
