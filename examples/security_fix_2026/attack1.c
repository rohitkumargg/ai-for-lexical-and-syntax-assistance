int system(char *command);
int main() {
    char cmd[50];
    scanf("%49s", cmd);
    system(cmd);
}
