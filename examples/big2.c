/* Generated 2000-line comprehensive benchmark file: big2.c */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Global structures and definitions */
struct Point {
    int x;
    int y;
};

struct DataRecord {
    int id;
    char name[64];
    double val;
};

int helper_add(int a, int b) {
    return a + b;
}

int helper_sub(int a, int b) {
    return a - b;
}

int helper_mul(int a, int b) {
    return a * b;
}

int test_lex_1(void) {
    int a = 1;
    int b = 2;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_2(void) {
    int x = 2
    int y = x + 10;
    return y;
}

int test_syn_bracket_3(void) {
    int arr[5;
    arr[0] = 3;
    return arr[0];
}

int test_syn_comma_4(void) {
    int sum = helper_add(10 20);
    return sum + 4;
}

int test_sem_dot_5(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 5;
    ptr.y = 6;
    return ptr.x + ptr.y;
}

int test_sec_gets_6(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_7(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 7 : 0;
}

int test_sec_sprintf_8(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 8);
    return msg[0] ? 1 : 0;
}

int test_lex_9(void) {
    int a = 9;
    int b = 18;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_10(void) {
    int x = 10
    int y = x + 10;
    return y;
}

int test_syn_bracket_11(void) {
    int arr[5;
    arr[0] = 11;
    return arr[0];
}

int test_syn_comma_12(void) {
    int sum = helper_add(10 20);
    return sum + 12;
}

int test_sem_dot_13(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 13;
    ptr.y = 14;
    return ptr.x + ptr.y;
}

int test_sec_gets_14(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_15(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 15 : 0;
}

int test_sec_sprintf_16(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 16);
    return msg[0] ? 1 : 0;
}

int test_lex_17(void) {
    int a = 17;
    int b = 34;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_18(void) {
    int x = 18
    int y = x + 10;
    return y;
}

int test_syn_bracket_19(void) {
    int arr[5;
    arr[0] = 19;
    return arr[0];
}

int test_syn_comma_20(void) {
    int sum = helper_add(10 20);
    return sum + 20;
}

int test_sem_dot_21(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 21;
    ptr.y = 22;
    return ptr.x + ptr.y;
}

int test_sec_gets_22(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_23(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 23 : 0;
}

int test_sec_sprintf_24(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 24);
    return msg[0] ? 1 : 0;
}

int test_lex_25(void) {
    int a = 25;
    int b = 50;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_26(void) {
    int x = 26
    int y = x + 10;
    return y;
}

int test_syn_bracket_27(void) {
    int arr[5;
    arr[0] = 27;
    return arr[0];
}

int test_syn_comma_28(void) {
    int sum = helper_add(10 20);
    return sum + 28;
}

int test_sem_dot_29(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 29;
    ptr.y = 30;
    return ptr.x + ptr.y;
}

int test_sec_gets_30(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_31(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 31 : 0;
}

int test_sec_sprintf_32(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 32);
    return msg[0] ? 1 : 0;
}

int test_lex_33(void) {
    int a = 33;
    int b = 66;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_34(void) {
    int x = 34
    int y = x + 10;
    return y;
}

int test_syn_bracket_35(void) {
    int arr[5;
    arr[0] = 35;
    return arr[0];
}

int test_syn_comma_36(void) {
    int sum = helper_add(10 20);
    return sum + 36;
}

int test_sem_dot_37(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 37;
    ptr.y = 38;
    return ptr.x + ptr.y;
}

int test_sec_gets_38(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_39(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 39 : 0;
}

int test_sec_sprintf_40(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 40);
    return msg[0] ? 1 : 0;
}

int test_lex_41(void) {
    int a = 41;
    int b = 82;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_42(void) {
    int x = 42
    int y = x + 10;
    return y;
}

int test_syn_bracket_43(void) {
    int arr[5;
    arr[0] = 43;
    return arr[0];
}

int test_syn_comma_44(void) {
    int sum = helper_add(10 20);
    return sum + 44;
}

int test_sem_dot_45(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 45;
    ptr.y = 46;
    return ptr.x + ptr.y;
}

int test_sec_gets_46(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_47(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 47 : 0;
}

int test_sec_sprintf_48(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 48);
    return msg[0] ? 1 : 0;
}

int test_lex_49(void) {
    int a = 49;
    int b = 98;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_50(void) {
    int x = 50
    int y = x + 10;
    return y;
}

int test_syn_bracket_51(void) {
    int arr[5;
    arr[0] = 51;
    return arr[0];
}

int test_syn_comma_52(void) {
    int sum = helper_add(10 20);
    return sum + 52;
}

int test_sem_dot_53(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 53;
    ptr.y = 54;
    return ptr.x + ptr.y;
}

int test_sec_gets_54(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_55(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 55 : 0;
}

int test_sec_sprintf_56(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 56);
    return msg[0] ? 1 : 0;
}

int test_lex_57(void) {
    int a = 57;
    int b = 114;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_58(void) {
    int x = 58
    int y = x + 10;
    return y;
}

int test_syn_bracket_59(void) {
    int arr[5;
    arr[0] = 59;
    return arr[0];
}

int test_syn_comma_60(void) {
    int sum = helper_add(10 20);
    return sum + 60;
}

int test_sem_dot_61(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 61;
    ptr.y = 62;
    return ptr.x + ptr.y;
}

int test_sec_gets_62(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_63(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 63 : 0;
}

int test_sec_sprintf_64(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 64);
    return msg[0] ? 1 : 0;
}

int test_lex_65(void) {
    int a = 65;
    int b = 130;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_66(void) {
    int x = 66
    int y = x + 10;
    return y;
}

int test_syn_bracket_67(void) {
    int arr[5;
    arr[0] = 67;
    return arr[0];
}

int test_syn_comma_68(void) {
    int sum = helper_add(10 20);
    return sum + 68;
}

int test_sem_dot_69(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 69;
    ptr.y = 70;
    return ptr.x + ptr.y;
}

int test_sec_gets_70(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_71(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 71 : 0;
}

int test_sec_sprintf_72(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 72);
    return msg[0] ? 1 : 0;
}

int test_lex_73(void) {
    int a = 73;
    int b = 146;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_74(void) {
    int x = 74
    int y = x + 10;
    return y;
}

int test_syn_bracket_75(void) {
    int arr[5;
    arr[0] = 75;
    return arr[0];
}

int test_syn_comma_76(void) {
    int sum = helper_add(10 20);
    return sum + 76;
}

int test_sem_dot_77(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 77;
    ptr.y = 78;
    return ptr.x + ptr.y;
}

int test_sec_gets_78(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_79(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 79 : 0;
}

int test_sec_sprintf_80(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 80);
    return msg[0] ? 1 : 0;
}

int test_lex_81(void) {
    int a = 81;
    int b = 162;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_82(void) {
    int x = 82
    int y = x + 10;
    return y;
}

int test_syn_bracket_83(void) {
    int arr[5;
    arr[0] = 83;
    return arr[0];
}

int test_syn_comma_84(void) {
    int sum = helper_add(10 20);
    return sum + 84;
}

int test_sem_dot_85(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 85;
    ptr.y = 86;
    return ptr.x + ptr.y;
}

int test_sec_gets_86(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_87(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 87 : 0;
}

int test_sec_sprintf_88(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 88);
    return msg[0] ? 1 : 0;
}

int test_lex_89(void) {
    int a = 89;
    int b = 178;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_90(void) {
    int x = 90
    int y = x + 10;
    return y;
}

int test_syn_bracket_91(void) {
    int arr[5;
    arr[0] = 91;
    return arr[0];
}

int test_syn_comma_92(void) {
    int sum = helper_add(10 20);
    return sum + 92;
}

int test_sem_dot_93(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 93;
    ptr.y = 94;
    return ptr.x + ptr.y;
}

int test_sec_gets_94(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_95(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 95 : 0;
}

int test_sec_sprintf_96(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 96);
    return msg[0] ? 1 : 0;
}

int test_lex_97(void) {
    int a = 97;
    int b = 194;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_98(void) {
    int x = 98
    int y = x + 10;
    return y;
}

int test_syn_bracket_99(void) {
    int arr[5;
    arr[0] = 99;
    return arr[0];
}

int test_syn_comma_100(void) {
    int sum = helper_add(10 20);
    return sum + 100;
}

int test_sem_dot_101(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 101;
    ptr.y = 102;
    return ptr.x + ptr.y;
}

int test_sec_gets_102(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_103(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 103 : 0;
}

int test_sec_sprintf_104(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 104);
    return msg[0] ? 1 : 0;
}

int test_lex_105(void) {
    int a = 105;
    int b = 210;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_106(void) {
    int x = 106
    int y = x + 10;
    return y;
}

int test_syn_bracket_107(void) {
    int arr[5;
    arr[0] = 107;
    return arr[0];
}

int test_syn_comma_108(void) {
    int sum = helper_add(10 20);
    return sum + 108;
}

int test_sem_dot_109(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 109;
    ptr.y = 110;
    return ptr.x + ptr.y;
}

int test_sec_gets_110(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_111(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 111 : 0;
}

int test_sec_sprintf_112(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 112);
    return msg[0] ? 1 : 0;
}

int test_lex_113(void) {
    int a = 113;
    int b = 226;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_114(void) {
    int x = 114
    int y = x + 10;
    return y;
}

int test_syn_bracket_115(void) {
    int arr[5;
    arr[0] = 115;
    return arr[0];
}

int test_syn_comma_116(void) {
    int sum = helper_add(10 20);
    return sum + 116;
}

int test_sem_dot_117(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 117;
    ptr.y = 118;
    return ptr.x + ptr.y;
}

int test_sec_gets_118(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_119(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 119 : 0;
}

int test_sec_sprintf_120(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 120);
    return msg[0] ? 1 : 0;
}

int test_lex_121(void) {
    int a = 121;
    int b = 242;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_122(void) {
    int x = 122
    int y = x + 10;
    return y;
}

int test_syn_bracket_123(void) {
    int arr[5;
    arr[0] = 123;
    return arr[0];
}

int test_syn_comma_124(void) {
    int sum = helper_add(10 20);
    return sum + 124;
}

int test_sem_dot_125(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 125;
    ptr.y = 126;
    return ptr.x + ptr.y;
}

int test_sec_gets_126(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_127(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 127 : 0;
}

int test_sec_sprintf_128(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 128);
    return msg[0] ? 1 : 0;
}

int test_lex_129(void) {
    int a = 129;
    int b = 258;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_130(void) {
    int x = 130
    int y = x + 10;
    return y;
}

int test_syn_bracket_131(void) {
    int arr[5;
    arr[0] = 131;
    return arr[0];
}

int test_syn_comma_132(void) {
    int sum = helper_add(10 20);
    return sum + 132;
}

int test_sem_dot_133(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 133;
    ptr.y = 134;
    return ptr.x + ptr.y;
}

int test_sec_gets_134(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_135(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 135 : 0;
}

int test_sec_sprintf_136(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 136);
    return msg[0] ? 1 : 0;
}

int test_lex_137(void) {
    int a = 137;
    int b = 274;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_138(void) {
    int x = 138
    int y = x + 10;
    return y;
}

int test_syn_bracket_139(void) {
    int arr[5;
    arr[0] = 139;
    return arr[0];
}

int test_syn_comma_140(void) {
    int sum = helper_add(10 20);
    return sum + 140;
}

int test_sem_dot_141(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 141;
    ptr.y = 142;
    return ptr.x + ptr.y;
}

int test_sec_gets_142(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_143(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 143 : 0;
}

int test_sec_sprintf_144(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 144);
    return msg[0] ? 1 : 0;
}

int test_lex_145(void) {
    int a = 145;
    int b = 290;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_146(void) {
    int x = 146
    int y = x + 10;
    return y;
}

int test_syn_bracket_147(void) {
    int arr[5;
    arr[0] = 147;
    return arr[0];
}

int test_syn_comma_148(void) {
    int sum = helper_add(10 20);
    return sum + 148;
}

int test_sem_dot_149(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 149;
    ptr.y = 150;
    return ptr.x + ptr.y;
}

int test_sec_gets_150(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_151(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 151 : 0;
}

int test_sec_sprintf_152(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 152);
    return msg[0] ? 1 : 0;
}

int test_lex_153(void) {
    int a = 153;
    int b = 306;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_154(void) {
    int x = 154
    int y = x + 10;
    return y;
}

int test_syn_bracket_155(void) {
    int arr[5;
    arr[0] = 155;
    return arr[0];
}

int test_syn_comma_156(void) {
    int sum = helper_add(10 20);
    return sum + 156;
}

int test_sem_dot_157(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 157;
    ptr.y = 158;
    return ptr.x + ptr.y;
}

int test_sec_gets_158(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_159(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 159 : 0;
}

int test_sec_sprintf_160(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 160);
    return msg[0] ? 1 : 0;
}

int test_lex_161(void) {
    int a = 161;
    int b = 322;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_162(void) {
    int x = 162
    int y = x + 10;
    return y;
}

int test_syn_bracket_163(void) {
    int arr[5;
    arr[0] = 163;
    return arr[0];
}

int test_syn_comma_164(void) {
    int sum = helper_add(10 20);
    return sum + 164;
}

int test_sem_dot_165(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 165;
    ptr.y = 166;
    return ptr.x + ptr.y;
}

int test_sec_gets_166(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_167(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 167 : 0;
}

int test_sec_sprintf_168(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 168);
    return msg[0] ? 1 : 0;
}

int test_lex_169(void) {
    int a = 169;
    int b = 338;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_170(void) {
    int x = 170
    int y = x + 10;
    return y;
}

int test_syn_bracket_171(void) {
    int arr[5;
    arr[0] = 171;
    return arr[0];
}

int test_syn_comma_172(void) {
    int sum = helper_add(10 20);
    return sum + 172;
}

int test_sem_dot_173(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 173;
    ptr.y = 174;
    return ptr.x + ptr.y;
}

int test_sec_gets_174(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_175(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 175 : 0;
}

int test_sec_sprintf_176(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 176);
    return msg[0] ? 1 : 0;
}

int test_lex_177(void) {
    int a = 177;
    int b = 354;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_178(void) {
    int x = 178
    int y = x + 10;
    return y;
}

int test_syn_bracket_179(void) {
    int arr[5;
    arr[0] = 179;
    return arr[0];
}

int test_syn_comma_180(void) {
    int sum = helper_add(10 20);
    return sum + 180;
}

int test_sem_dot_181(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 181;
    ptr.y = 182;
    return ptr.x + ptr.y;
}

int test_sec_gets_182(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_183(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 183 : 0;
}

int test_sec_sprintf_184(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 184);
    return msg[0] ? 1 : 0;
}

int test_lex_185(void) {
    int a = 185;
    int b = 370;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_186(void) {
    int x = 186
    int y = x + 10;
    return y;
}

int test_syn_bracket_187(void) {
    int arr[5;
    arr[0] = 187;
    return arr[0];
}

int test_syn_comma_188(void) {
    int sum = helper_add(10 20);
    return sum + 188;
}

int test_sem_dot_189(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 189;
    ptr.y = 190;
    return ptr.x + ptr.y;
}

int test_sec_gets_190(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_191(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 191 : 0;
}

int test_sec_sprintf_192(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 192);
    return msg[0] ? 1 : 0;
}

int test_lex_193(void) {
    int a = 193;
    int b = 386;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_194(void) {
    int x = 194
    int y = x + 10;
    return y;
}

int test_syn_bracket_195(void) {
    int arr[5;
    arr[0] = 195;
    return arr[0];
}

int test_syn_comma_196(void) {
    int sum = helper_add(10 20);
    return sum + 196;
}

int test_sem_dot_197(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 197;
    ptr.y = 198;
    return ptr.x + ptr.y;
}

int test_sec_gets_198(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_199(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 199 : 0;
}

int test_sec_sprintf_200(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 200);
    return msg[0] ? 1 : 0;
}

int test_lex_201(void) {
    int a = 201;
    int b = 402;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_202(void) {
    int x = 202
    int y = x + 10;
    return y;
}

int test_syn_bracket_203(void) {
    int arr[5;
    arr[0] = 203;
    return arr[0];
}

int test_syn_comma_204(void) {
    int sum = helper_add(10 20);
    return sum + 204;
}

int test_sem_dot_205(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 205;
    ptr.y = 206;
    return ptr.x + ptr.y;
}

int test_sec_gets_206(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_207(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 207 : 0;
}

int test_sec_sprintf_208(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 208);
    return msg[0] ? 1 : 0;
}

int test_lex_209(void) {
    int a = 209;
    int b = 418;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_210(void) {
    int x = 210
    int y = x + 10;
    return y;
}

int test_syn_bracket_211(void) {
    int arr[5;
    arr[0] = 211;
    return arr[0];
}

int test_syn_comma_212(void) {
    int sum = helper_add(10 20);
    return sum + 212;
}

int test_sem_dot_213(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 213;
    ptr.y = 214;
    return ptr.x + ptr.y;
}

int test_sec_gets_214(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_215(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 215 : 0;
}

int test_sec_sprintf_216(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 216);
    return msg[0] ? 1 : 0;
}

int test_lex_217(void) {
    int a = 217;
    int b = 434;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_218(void) {
    int x = 218
    int y = x + 10;
    return y;
}

int test_syn_bracket_219(void) {
    int arr[5;
    arr[0] = 219;
    return arr[0];
}

int test_syn_comma_220(void) {
    int sum = helper_add(10 20);
    return sum + 220;
}

int test_sem_dot_221(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 221;
    ptr.y = 222;
    return ptr.x + ptr.y;
}

int test_sec_gets_222(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_223(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 223 : 0;
}

int test_sec_sprintf_224(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 224);
    return msg[0] ? 1 : 0;
}

int test_lex_225(void) {
    int a = 225;
    int b = 450;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_226(void) {
    int x = 226
    int y = x + 10;
    return y;
}

int test_syn_bracket_227(void) {
    int arr[5;
    arr[0] = 227;
    return arr[0];
}

int test_syn_comma_228(void) {
    int sum = helper_add(10 20);
    return sum + 228;
}

int test_sem_dot_229(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 229;
    ptr.y = 230;
    return ptr.x + ptr.y;
}

int test_sec_gets_230(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_231(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 231 : 0;
}

int test_sec_sprintf_232(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 232);
    return msg[0] ? 1 : 0;
}

int test_lex_233(void) {
    int a = 233;
    int b = 466;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_234(void) {
    int x = 234
    int y = x + 10;
    return y;
}

int test_syn_bracket_235(void) {
    int arr[5;
    arr[0] = 235;
    return arr[0];
}

int test_syn_comma_236(void) {
    int sum = helper_add(10 20);
    return sum + 236;
}

int test_sem_dot_237(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 237;
    ptr.y = 238;
    return ptr.x + ptr.y;
}

int test_sec_gets_238(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_239(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 239 : 0;
}

int test_sec_sprintf_240(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 240);
    return msg[0] ? 1 : 0;
}

int test_lex_241(void) {
    int a = 241;
    int b = 482;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_242(void) {
    int x = 242
    int y = x + 10;
    return y;
}

int test_syn_bracket_243(void) {
    int arr[5;
    arr[0] = 243;
    return arr[0];
}

int test_syn_comma_244(void) {
    int sum = helper_add(10 20);
    return sum + 244;
}

int test_sem_dot_245(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 245;
    ptr.y = 246;
    return ptr.x + ptr.y;
}

int test_sec_gets_246(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_247(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 247 : 0;
}

int test_sec_sprintf_248(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 248);
    return msg[0] ? 1 : 0;
}

int test_lex_249(void) {
    int a = 249;
    int b = 498;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_250(void) {
    int x = 250
    int y = x + 10;
    return y;
}

int test_syn_bracket_251(void) {
    int arr[5;
    arr[0] = 251;
    return arr[0];
}

int test_syn_comma_252(void) {
    int sum = helper_add(10 20);
    return sum + 252;
}

int test_sem_dot_253(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 253;
    ptr.y = 254;
    return ptr.x + ptr.y;
}

int test_sec_gets_254(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_255(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 255 : 0;
}

int test_sec_sprintf_256(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 256);
    return msg[0] ? 1 : 0;
}

int test_lex_257(void) {
    int a = 257;
    int b = 514;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_258(void) {
    int x = 258
    int y = x + 10;
    return y;
}

int test_syn_bracket_259(void) {
    int arr[5;
    arr[0] = 259;
    return arr[0];
}

int test_syn_comma_260(void) {
    int sum = helper_add(10 20);
    return sum + 260;
}

int test_sem_dot_261(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 261;
    ptr.y = 262;
    return ptr.x + ptr.y;
}

int test_sec_gets_262(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_263(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 263 : 0;
}

int test_sec_sprintf_264(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 264);
    return msg[0] ? 1 : 0;
}

int test_lex_265(void) {
    int a = 265;
    int b = 530;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_266(void) {
    int x = 266
    int y = x + 10;
    return y;
}

int test_syn_bracket_267(void) {
    int arr[5;
    arr[0] = 267;
    return arr[0];
}

int test_syn_comma_268(void) {
    int sum = helper_add(10 20);
    return sum + 268;
}

int test_sem_dot_269(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 269;
    ptr.y = 270;
    return ptr.x + ptr.y;
}

int test_sec_gets_270(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_271(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 271 : 0;
}

int test_sec_sprintf_272(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 272);
    return msg[0] ? 1 : 0;
}

int test_lex_273(void) {
    int a = 273;
    int b = 546;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_274(void) {
    int x = 274
    int y = x + 10;
    return y;
}

int test_syn_bracket_275(void) {
    int arr[5;
    arr[0] = 275;
    return arr[0];
}

int test_syn_comma_276(void) {
    int sum = helper_add(10 20);
    return sum + 276;
}

int test_sem_dot_277(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 277;
    ptr.y = 278;
    return ptr.x + ptr.y;
}

int test_sec_gets_278(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_279(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 279 : 0;
}

int test_sec_sprintf_280(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 280);
    return msg[0] ? 1 : 0;
}

int test_lex_281(void) {
    int a = 281;
    int b = 562;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_282(void) {
    int x = 282
    int y = x + 10;
    return y;
}

int test_syn_bracket_283(void) {
    int arr[5;
    arr[0] = 283;
    return arr[0];
}

int test_syn_comma_284(void) {
    int sum = helper_add(10 20);
    return sum + 284;
}

int test_sem_dot_285(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 285;
    ptr.y = 286;
    return ptr.x + ptr.y;
}

int test_sec_gets_286(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_287(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 287 : 0;
}

int test_sec_sprintf_288(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 288);
    return msg[0] ? 1 : 0;
}

int test_lex_289(void) {
    int a = 289;
    int b = 578;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_290(void) {
    int x = 290
    int y = x + 10;
    return y;
}

int test_syn_bracket_291(void) {
    int arr[5;
    arr[0] = 291;
    return arr[0];
}

int test_syn_comma_292(void) {
    int sum = helper_add(10 20);
    return sum + 292;
}

int test_sem_dot_293(void) {
    struct Point p;
    struct Point *ptr = &p;
    ptr.x = 293;
    ptr.y = 294;
    return ptr.x + ptr.y;
}

int test_sec_gets_294(void) {
    char buf[64];
    gets(buf);
    return buf[0] == 'A' ? 1 : 0;
}

int test_sec_scanf_295(void) {
    char name[32];
    scanf("%s", name);
    return name[0] ? 295 : 0;
}

int test_sec_sprintf_296(void) {
    char msg[128];
    sprintf(msg, "Record ID: %d", 296);
    return msg[0] ? 1 : 0;
}

int test_lex_297(void) {
    int a = 297;
    int b = 594;
    int res = 0;
    if (a === b) {
        res = 1;
    }
    return res;
}

int test_syn_semi_298(void) {
    int x = 298
    int y = x + 10;
    return y;
}

int test_syn_bracket_299(void) {
    int arr[5;
    arr[0] = 299;
    return arr[0];
}

int test_syn_comma_300(void) {
    int sum = helper_add(10 20);
    return sum + 300;
}

int main(void) {
    int total = 0;
    total += test_lex_1();
    total += test_syn_semi_2();
    total += test_syn_bracket_3();
    total += test_syn_comma_4();
    total += test_sem_dot_5();
    total += test_sec_gets_6();
    total += test_sec_scanf_7();
    total += test_sec_sprintf_8();
    printf("Total: %d\n", total);
    return 0;
}
