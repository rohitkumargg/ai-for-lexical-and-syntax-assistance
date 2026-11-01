# P6: Agent-Manipulation Detection Generalization Report

## Evaluation Summary
- **Total Test Cases**: 455 (416 positives, 39 negatives)
- **Precision**: 100.00%
- **Recall**: 90.38%
- **F1 Score**: 94.95%
- **Accuracy**: 91.21%
- **False Positives**: 0 (out of 39 benign cases)
- **False Negatives**: 40 (out of 416 adversarial cases)

## Breakdown by Template Family
See [`per_family_table.md`](per_family_table.md) for individual family metrics across the 5 training families and 3 held-out families.

## Epistemological Limitations of Generalization Measurement
Static testing against a fixed evaluation distribution can prove the presence of generalized pattern recognition within the evaluated manifold, but it fundamentally cannot prove universal robustness against out-of-distribution adversarial attacks. Because natural language and programming syntax form an open-ended semantic space, an attacker with white-box or gray-box knowledge of the detector can synthesize novel steganographic encodings, semantic circumlocutions, or multi-turn prompt injections that decouple the lexical markers ($A, I, T$) while retaining pragmatic intent. Consequently, while our multi-layer architecture (L1 structural co-occurrence, L2 isolated local LLM classification, and L3 behavioral cross-checking with AI prompt masking) raises the attacker's required work factor substantially above naive regex matching, empirical generalization metrics should be understood as empirical lower bounds under defined carrier transformations rather than mathematical guarantees of safety.
