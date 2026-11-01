# Compiler Error Correction & Security Analysis Engine

## Overview
This engine provides intelligent lexical, syntactic, semantic, and security analysis and automated repair for C and Python source code.

## Known Limitations and Static Analysis Boundaries

### 1. SEC-01 Integer Overflow: Inter-Statement Dataflow Limitations
- **Current Capability**: The SEC-01 static rule analyzer inspects AST expression trees within declaration initializers and assignment statements. It accurately evaluates constant expressions (e.g. `2147483647 + 1`), detect missing widening casts before promotion (e.g. `(long long)(a + b)`), and catches constant boundary violations.
- **Documented Known Gap (Row 6)**: For sequential statements such as:
  ```c
  int x = 2147483647;
  x += 1;
  ```
  The constant evaluator does not maintain an inter-statement abstract interpretation domain across subsequent compound assignment operators (`+=`, `-=`). Consequently, `x += 1` is not flagged as an overflow without single-block constant propagation across statements. This is a documented known limitation.

### 2. Unsigned Integer Arithmetic & Overflow Policy (Row 3)
- **C Standard Definition**: Per ISO/IEC 9899:1999 (C99) §6.2.5, paragraph 9:
  > *"A computation involving unsigned operands can never overflow, because a result that cannot be represented by the resulting unsigned integer type is reduced modulo the number that is one greater than the largest value that can be represented by the resulting type."*
- **Engine Policy**: 
  - Signed integer overflow is undefined behavior (UB) in C and is classified as **CONFIRMED / HIGH**.
  - Unsigned wraparound is strictly defined behavior in C. In security-sensitive contexts (such as allocation size computations), intentional or unintended modular wraparound can lead to downstream buffer underflows (CWE-190).
  - Recommended Classification: **POSSIBLE / MEDIUM** with an explanatory note stating that while unsigned wraparound is well-defined by the C standard, wraparound in boundary expressions may indicate unintended truncation or logic errors.
