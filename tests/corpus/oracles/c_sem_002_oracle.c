struct Point { int x; };
struct Point helper(void) { struct Point p = {1}; return p; }
int main(void) {
    struct Point res = helper();
    return res.x;
}
