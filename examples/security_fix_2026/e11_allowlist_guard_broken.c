int system(char *command);
int main() {
    char cmd[20];
    scanf("%19s", cmd);
    if (strcmp(cmd, "ls") == 0) {
        system(cmd);
    }
    return 0;
}
