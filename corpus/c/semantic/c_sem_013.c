struct User {
    int id;
    int age;
};
int main(void) {
    struct User u = {1, 30};
    return u.score;
}
