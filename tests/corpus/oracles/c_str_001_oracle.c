struct Point { int x; int y; };
struct Rect { struct Point tl; struct Point br; };
int main(void) {
    struct Rect r = {{0, 0}, {10, 10}};
    return r.br.x;
}
