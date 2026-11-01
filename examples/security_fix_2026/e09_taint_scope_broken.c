int system(char *command);
int run_a() {
    char cmd[40];
    scanf("%39s", cmd);
    return 0;
}
int run_b() {
    char cmd[40] = "ls";
    system(cmd);
    return 0;
}
