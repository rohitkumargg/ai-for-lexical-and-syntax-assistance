# scripts/held_out_evaluation_v2.py
import os
import sys
import random
import time
from typing import List, Dict, Any, Tuple

sys.path.insert(0, os.getcwd())

from compiler.repair_job_manager import RepairJobManager, check_c_syntax_errors, split_top_level_functions
from compiler.repair_planner import RepairPlanner
from compiler.patch_validator import SandboxedCompiler, PatchIntegrityInspector
from compiler.agents import SyntaxAgent

# Seed 4242 as mandated for fresh unseen evaluation
random.seed(4242)

CLEAN_TEMPLATES_V2 = [
    # Program 1: Matrix Operations (~110 lines)
    """#include <stdio.h>

void matrix_zero(int mat[3][3]) {
    for (int r = 0; r < 3; r++) {
        for (int c = 0; c < 3; c++) {
            mat[r][c] = 0;
        }
    }
}

void matrix_identity(int mat[3][3]) {
    for (int r = 0; r < 3; r++) {
        for (int c = 0; c < 3; c++) {
            if (r == c) {
                mat[r][c] = 1;
            } else {
                mat[r][c] = 0;
            }
        }
    }
}

int matrix_trace(int mat[3][3]) {
    int tr = 0;
    for (int i = 0; i < 3; i++) {
        tr = tr + mat[i][i];
    }
    return tr;
}

void matrix_multiply(int a[3][3], int b[3][3], int out[3][3]) {
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            out[i][j] = 0;
            for (int k = 0; k < 3; k++) {
                out[i][j] = out[i][j] + a[i][k] * b[k][j];
            }
        }
    }
}

int is_symmetric(int mat[3][3]) {
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            if (mat[i][j] != mat[j][i]) {
                return 0;
            }
        }
    }
    return 1;
}

int main(void) {
    int m1[3][3];
    int m2[3][3];
    int res[3][3];
    matrix_identity(m1);
    matrix_identity(m2);
    matrix_multiply(m1, m2, res);
    int tr = matrix_trace(res);
    printf("Trace: %d, Symmetric: %d\\n", tr, is_symmetric(res));
    return 0;
}
""",
    # Program 2: Array Statistics & Sorting (~95 lines)
    """#include <stdio.h>

void swap_values(int *x, int *y) {
    int temp = *x;
    *x = *y;
    *y = temp;
}

void bubble_sort(int arr[], int n) {
    for (int i = 0; i < n - 1; i++) {
        for (int j = 0; j < n - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                swap_values(&arr[j], &arr[j + 1]);
            }
        }
    }
}

int calculate_median(int arr[], int n) {
    bubble_sort(arr, n);
    return arr[n / 2];
}

int count_greater_than(int arr[], int n, int threshold) {
    int count = 0;
    for (int i = 0; i < n; i++) {
        if (arr[i] > threshold) {
            count = count + 1;
        }
    }
    return count;
}

int main(void) {
    int data[7] = {14, 3, 29, 8, 1, 42, 19};
    int med = calculate_median(data, 7);
    int cnt = count_greater_than(data, 7, 10);
    printf("Median: %d, Greater: %d\\n", med, cnt);
    return 0;
}
""",
    # Program 3: Geometry & Coordinate Math (~90 lines)
    """#include <stdio.h>

int integer_square(int n) {
    return n * n;
}

int distance_squared(int x1, int y1, int x2, int y2) {
    int dx = x2 - x1;
    int dy = y2 - y1;
    return integer_square(dx) + integer_square(dy);
}

int point_in_bounding_box(int px, int py, int min_x, int min_y, int max_x, int max_y) {
    if (px >= min_x && px <= max_x) {
        if (py >= min_y && py <= max_y) {
            return 1;
        }
    }
    return 0;
}

int perimeter_box(int width, int height) {
    return 2 * (width + height);
}

int main(void) {
    int d2 = distance_squared(0, 0, 3, 4);
    int inside = point_in_bounding_box(2, 3, 0, 0, 5, 5);
    int p = perimeter_box(10, 20);
    printf("D2: %d, Inside: %d, Perimeter: %d\\n", d2, inside, p);
    return 0;
}
"""
]

ERROR_CLASSES = [
    "missing_paren",
    "extra_paren",
    "missing_brace",
    "misspelled_identifier",
    "missing_comma",
    "stray_token",
]

def inject_error_v2(source: str, error_class: str, variant_idx: int) -> Tuple[str, int]:
    lines = source.splitlines(keepends=True)
    defect_line = 1

    if error_class == "missing_paren":
        for idx in range(len(lines)):
            if "if (" in lines[idx] and ")" in lines[idx]:
                lines[idx] = lines[idx].replace(")", "", 1)
                defect_line = idx + 1
                break
    elif error_class == "extra_paren":
        for idx in range(len(lines)):
            if "for (" in lines[idx]:
                lines[idx] = lines[idx].replace("for (", "for ((", 1)
                defect_line = idx + 1
                break
            elif "if (" in lines[idx]:
                lines[idx] = lines[idx].replace("if (", "if ((", 1)
                defect_line = idx + 1
                break
    elif error_class == "missing_brace":
        # Remove a closing brace of an inner loop or if block
        for idx in range(len(lines)):
            if lines[idx].strip() == "}":
                lines[idx] = ""
                defect_line = idx + 1
                break
    elif error_class == "misspelled_identifier":
        for idx in range(len(lines)):
            if "int tr = 0;" in lines[idx]:
                lines[idx] = lines[idx].replace("int tr", "int txr", 1)
                defect_line = idx + 1
                break
            elif "int count = 0;" in lines[idx]:
                lines[idx] = lines[idx].replace("int count", "int cound", 1)
                defect_line = idx + 1
                break
            elif "int temp = *x;" in lines[idx]:
                lines[idx] = lines[idx].replace("int temp", "int tmpz", 1)
                defect_line = idx + 1
                break
            elif "int dx = x2 - x1;" in lines[idx]:
                lines[idx] = lines[idx].replace("int dx", "int dxx", 1)
                defect_line = idx + 1
                break
    elif error_class == "missing_comma":
        for idx in range(len(lines)):
            if "matrix_multiply(m1, m2, res);" in lines[idx]:
                lines[idx] = lines[idx].replace("m1, m2", "m1 m2", 1)
                defect_line = idx + 1
                break
            elif "count_greater_than(data, 7, 10);" in lines[idx]:
                lines[idx] = lines[idx].replace("7, 10", "7 10", 1)
                defect_line = idx + 1
                break
            elif "distance_squared(0, 0, 3, 4);" in lines[idx]:
                lines[idx] = lines[idx].replace("3, 4", "3 4", 1)
                defect_line = idx + 1
                break
            elif "perimeter_box(10, 20);" in lines[idx]:
                lines[idx] = lines[idx].replace("10, 20", "10 20", 1)
                defect_line = idx + 1
                break
    elif error_class == "stray_token":
        for idx in range(len(lines)):
            if "return tr;" in lines[idx]:
                lines[idx] = "    @\n" + lines[idx]
                defect_line = idx + 1
                break
            elif "return arr[n / 2];" in lines[idx]:
                lines[idx] = "    @\n" + lines[idx]
                defect_line = idx + 1
                break
            elif "return 2 * (width + height);" in lines[idx]:
                lines[idx] = "    @\n" + lines[idx]
                defect_line = idx + 1
                break

    return "".join(lines), defect_line

def generate_programs_v2() -> List[Dict[str, Any]]:
    programs = []
    prog_id = 1
    for err_class in ERROR_CLASSES:
        for i in range(5):
            tmpl = CLEAN_TEMPLATES_V2[i % len(CLEAN_TEMPLATES_V2)]
            broken_src, d_line = inject_error_v2(tmpl, err_class, i)
            # Balanced split: 2 or 3 per class
            split = "dev" if i in (0, 1) or (i == 4 and prog_id % 2 == 1) else "unseen"
            programs.append({
                "id": f"v2_prog_{prog_id:02d}",
                "error_class": err_class,
                "variant": i,
                "code": broken_src,
                "defect_line": d_line,
                "clean_base": tmpl,
                "split": split,
            })
            prog_id += 1
    return programs

if __name__ == "__main__":
    progs = generate_programs_v2()
    print(f"Generated {len(progs)} fresh evaluation programs.")
    devs = [p for p in progs if p['split'] == 'dev']
    unseens = [p for p in progs if p['split'] == 'unseen']
    print(f"Split: {len(devs)} dev / {len(unseens)} unseen")
    from collections import Counter
    print("Unseen distribution:", Counter(p['error_class'] for p in unseens))
