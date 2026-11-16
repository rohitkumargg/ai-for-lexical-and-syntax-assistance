struct Point { int x; };
int main(void) {
    struct Point res = helper();
    return res.x;
}
