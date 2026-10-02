import sys, re
sys.path.insert(0, ".")
from test_parser import parse_source, has_any_errors
from compiler.semantic_checker import SemanticChecker

# 1. Test undeclared
seed1 = """int main() {
    int x = 1;
    int y = 2;
    int z = x + y;
    return z;
}"""

buggy_und = """int main() {
    int x = 1;
    int y = 2;
    int z = x + ext_val;
    return z;
}"""

t1, l1, _ = parse_source(buggy_und, "t1")
sc1 = SemanticChecker()
sc1.visit(t1)
print("Undeclared issues:", [(i.get("kind"), i.get("name"), i.get("line")) for i in sc1.get_issues()])

# 2. Test redeclared
buggy_redecl = """int main() {
    int x = 1;
    int x = 2;
    return x;
}"""

t2, l2, _ = parse_source(buggy_redecl, "t2")
sc2 = SemanticChecker()
sc2.visit(t2)
print("Redeclared issues:", [(i.get("kind"), i.get("name"), i.get("line")) for i in sc2.get_issues()])

# 3. Test unknown_member
seed3 = """struct Point {
    int x;
    int y;
};
int main() {
    struct Point p;
    p.x = 10;
    p.y = 20;
    return p.x + p.y;
}"""

buggy_member = """struct Point {
    int x;
    int y;
};
int main() {
    struct Point p;
    p.z = 10;
    p.y = 20;
    return p.x + p.y;
}"""

t3, l3, _ = parse_source(buggy_member, "t3")
sc3 = SemanticChecker()
sc3.visit(t3)
print("Unknown member issues:", [(i.get("kind"), i.get("name"), i.get("line")) for i in sc3.get_issues()])
