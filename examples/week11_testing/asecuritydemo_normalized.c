int helper_add(int a, int b) {
    return a + b;
}

int helper_mul(int a, int b) {
    return a * b;
}

int helper_sum_array(int arr[], int n) {
    int i = 0;
    int s = 0;
    while (i < n) {
        s = s + arr[i];
        i = i + 1;
    }
    return s;
}

int helper_max(int arr[], int n) {
    int i = 1;
    int m = arr[0];
    while (i < n) {
        if (arr[i] > m) {
            m = arr[i];
        }
        i = i + 1;
    }
    return m;
}

int vuln_system_1() {
    char cmd[100];
    scanf("%11s", cmd);
    system(cmd);
    return 0;
}

int vuln_gets_1() {
    char buf[100];
    scanf("%11s", buf);
    return 0;
}

int vuln_mixed_1() {
    int a = 5;
    char buf[100];
    scanf("%11s", buf);
    return a;
}

int vuln_typo_main_style() {
    char cmd[50];
    scanf("%11s", cmd);
    system(cmd);
    return 0;
}

int vuln_system_2() {
    char cmd[100];
    scanf("%11s", cmd);
    system(cmd);
    return 0;
}

int vuln_gets_2() {
    char s[20];
    int a = 0;
    scanf("%11s", s);
    a = a + 1;
    return a;
}

int vuln_scnaf_1() {
    char s[10];
    scanf("%11s", s);
    return 0;
}

int vuln_sprintf_1() {
    char s[20];
    scanf("%11s", s);
    return 0;
}

int vuln_system_3() {
    char cmd[100];
    scanf("%11s", cmd);
    system(cmd);
    return 0;
}

int vuln_sprintf_2() {
    char s[20];
    scanf("%11s", s);
    return 0;
}

int vuln_gets_3() {
    char s[10];
    scanf("%11s", s);
    return 0;
}

int vuln_strcpy_1() {
    char dst[10];
    char src[20];
    scanf("%11s", src);
    return 0;
}

int vuln_combo_1() {
    char name[32];
    char out[16];
    scanf("%11s", name);
    scanf("%11s", out);
    return 0;
}

int vuln_combo_2() {
    char cmd[80];
    char logbuf[30];
    scanf("%11s", cmd);
    scanf("%11s", logbuf);
    system(cmd);
    return 0;
}

int vuln_combo_3() {
    char a[10];
    char b[40];
    scanf("%11s", a);
    scanf("%11s", b);
    return 0;
}

int vuln_combo_4() {
    char user[20];
    char msg[20];
    scanf("%11s", user);
    scanf("%11s", msg);
    return 0;
}

int vuln_combo_5() {
    char cmd[60];
    scanf("%11s", cmd);
    system(cmd);
    return 0;
}

int vuln_combo_6() {
    char one[8];
    char two[50];
    scanf("%11s", one);
    scanf("%11s", two);
    return 0;
}

int vuln_combo_7() {
    char data[12];
    scanf("%11s", data);
    return 0;
}

int vuln_combo_8() {
    char source[30];
    char dest[10];
    scanf("%11s", source);
    scanf("%11s", dest);
    return 0;
}

int vuln_combo_9() {
    int x = 10;
    char cmd[100];
    scanf("%11s", cmd);
    system(cmd);
    return x;
}

int vuln_combo_10() {
    char s[15];
    scanf("%11s", s);
    scanf("%11s", s);
    return 0;
}

int batch_1() {
    int total = 0;
    total = total + vuln_system_1();
    total = total + vuln_gets_1();
    total = total + vuln_mixed_1();
    return total;
}

int batch_2() {
    int total = 0;
    total = total + vuln_typo_main_style();
    total = total + vuln_system_2();
    total = total + vuln_gets_2();
    return total;
}

int batch_3() {
    int total = 0;
    total = total + vuln_scnaf_1();
    total = total + vuln_sprintf_1();
    total = total + vuln_system_3();
    return total;
}

int batch_4() {
    int total = 0;
    total = total + vuln_sprintf_2();
    total = total + vuln_gets_3();
    total = total + vuln_strcpy_1();
    return total;
}

int batch_5() {
    int total = 0;
    total = total + vuln_combo_1();
    total = total + vuln_combo_2();
    total = total + vuln_combo_3();
    return total;
}

int batch_6() {
    int total = 0;
    total = total + vuln_combo_4();
    total = total + vuln_combo_5();
    total = total + vuln_combo_6();
    return total;
}

int batch_7() {
    int total = 0;
    total = total + vuln_combo_7();
    total = total + vuln_combo_8();
    total = total + vuln_combo_9();
    total = total + vuln_combo_10();
    return total;
}

int scenario_1(int n) {
    char cmd[100];
    int score = 0;
    scanf("%11s", cmd);
    system(cmd);
    while (n > 0) {
        score = score + n;
        n = n - 1;
    }
    return score;
}

int scenario_2(int n) {
    char s[20];
    int arr[5];
    arr[0] = 1;
    arr[1] = 2;
    arr[2] = 3;
    arr[3] = 4;
    arr[4] = 5;
    scanf("%11s", arr);
    return helper_sum_array(arr, 5) + n;
}

int scenario_3() {
    char dst[10];
    char src[100];
    scanf("%11s", src);
    scanf("%11s", dst);
    return 0;
}

int scenario_4() {
    char s[20];
    scanf("%11s", s);
    return 0;
}

int scenario_5() {
    char s[10];
    scanf("%11s", s);
    return 0;
}

int scenario_6() {
    int a = 5;
    char cmd[50];
    scanf("%11s", cmd);
    system(cmd);
    return a;
}

int scenario_7() {
    char line[25];
    scanf("%11s", line);
    return 0;
}

int scenario_8() {
    char cmd[120];
    scanf("%11s", cmd);
    system(cmd);
    return 0;
}

int scenario_9() {
    char a[12];
    char b[24];
    scanf("%11s", a);
    return 0;
}

int scenario_10() {
    char x[20];
    scanf("%11s", x);
    return 0;
}

int contest_block_1() {
    int ans = 0;
    ans = ans + scenario_1(5);
    ans = ans + scenario_2(3);
    ans = ans + scenario_3();
    return ans;
}

int contest_block_2() {
    int ans = 0;
    ans = ans + scenario_4();
    ans = ans + scenario_5();
    ans = ans + scenario_6();
    return ans;
}

int contest_block_3() {
    int ans = 0;
    ans = ans + scenario_7();
    ans = ans + scenario_8();
    ans = ans + scenario_9();
    ans = ans + scenario_10();
    return ans;
}

int main() {
    int total = 0;
    int scores[6];
    int i = 0;

    scores[0] = batch_1();
    scores[1] = batch_2();
    scores[2] = batch_3();
    scores[3] = batch_4();
    scores[4] = batch_5();
    scores[5] = batch_6();

    i = 0;
    while (i < 6) {
        total = total + scores[i];
        i = i + 1;
    }

    total = total + batch_7();
    total = total + contest_block_1();
    total = total + contest_block_2();
    total = total + contest_block_3();

    if (total > 100) {
        total = total - helper_max(scores, 6);
    } else {
        total = total + helper_add(1, 2);
    }

    total = total + helper_mul(2, 3);

    return total;
}
