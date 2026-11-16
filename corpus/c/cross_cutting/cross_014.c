struct Node { int val; struct Node *next; };
int main(void) {
    struct Node n = {42, 0};
    struct Node *p = &n;
    return p->val
}
