struct Point {
    int x;
    int y;
};

int main() {
    struct Point pt;
    pt->x = 20;
    return pt.x;
}
