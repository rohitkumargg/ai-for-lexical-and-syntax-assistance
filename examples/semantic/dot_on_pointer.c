struct Point {
    int x;
    int y;
};

int main() {
    struct Point pt;
    struct Point *p = &pt;
    p.x = 10;
    return p->x;
}
