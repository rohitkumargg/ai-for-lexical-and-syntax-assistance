/*
 * 00_sim_1_cascading_hallucination.c
 *
 * Simulates a CASCADING HALLUCINATION in a 5-stage agent pipeline:
 *
 *   Researcher -> Analyst -> Planner -> Coder -> Reviewer
 *
 * A single fabricated fact is seeded at stage 0 (a library function that
 * does not exist). Every downstream stage trusts the stage before it, builds
 * on the fabricated claim, and RAISES confidence instead of re-checking it.
 * By the Reviewer stage a false claim sits at ~98% confidence and has been
 * "approved". The Coder stage also bakes in a concrete defect: a buffer size
 * declared as 8192 for a 256-byte buffer (simulated, no real memory is
 * corrupted).
 *
 * Modes:
 *   ./sim                 unmitigated pipeline (the attack succeeds)
 *   ./sim --verify        each claim is checked against ground truth before
 *                         downstream stages may use it (cascade is stopped)
 *   ./sim --boost 0.05    change per-stage confidence inflation (default 0.10)
 *
 * Exit code: 0 = no false claim reached the Reviewer, 1 = cascade reached the
 * final stage, 2 = bad arguments. Handy for wiring into a test harness.
 *
 * Build: gcc -Wall -Wextra -O2 -o sim 00_sim_1_cascading_hallucination.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define N_STAGES 5
#define N_CLAIMS 16
#define CONF_CAP 0.99
#define BUF_ACTUAL 256
#define BUF_DECLARED 8192

typedef struct {
  int id;
  int stage;       /* pipeline stage that emits this claim        */
  int parent;      /* claim this one is derived from, -1 = root   */
  const char *key; /* canonical fact key (verifier looks this up) */
  const char *text;
  int is_true;      /* ground truth, hidden from the "agents"      */
  double base_conf; /* only used for root claims                   */
} Claim;

/* Per-claim runtime state, kept separate from the static claim table. */
typedef struct {
  int emitted;
  int quarantined;
  double conf;
} State;

static const char *STAGE_NAME[N_STAGES] = {"Researcher", "Analyst", "Planner",
                                           "Coder", "Reviewer"};

/* Facts the verifier can confirm. Hallucinated keys are deliberately absent. */
static const char *GROUND_TRUTH[] = {
    "openssl.EVP_EncryptInit_ex",
    "posix.snprintf",
    "openssl.evp_requires_ctx",
    "posix.snprintf_nul",
    "plan.ctx_alloc",
    "code.ctx_new",
    "review.ctx_ok",
};

static Claim claims[N_CLAIMS] = {
    /* ---- Stage 0: Researcher ---------------------------------------- */
    {0, 0, -1, "openssl.EVP_EncryptInit_ex",
     "OpenSSL exposes EVP_EncryptInit_ex() for symmetric encryption", 1, 0.93},
    {1, 0, -1, "posix.snprintf",
     "POSIX defines snprintf() as a size-bounded write", 1, 0.95},
    /* [HALLUCINATION SEED] libsecurefmt / secure_sprintf_s() do not exist */
    {2, 0, -1, "libsecurefmt.secure_sprintf_s",
     "libsecurefmt 3.2 exports secure_sprintf_s()", 0, 0.58},

    /* ---- Stage 1: Analyst ------------------------------------------- */
    /* [CASCADE] built on claim 2 */
    {3, 1, 2, "libsecurefmt.bounds_checked",
     "secure_sprintf_s() is bounds-checked and safe for untrusted input", 0, 0},
    /* [CASCADE] built on claim 2 (fabricated authority) */
    {4, 1, 2, "libsecurefmt.cert_approved",
     "libsecurefmt is endorsed by CERT C secure-coding guidance", 0, 0},
    {5, 1, 0, "openssl.evp_requires_ctx",
     "EVP_EncryptInit_ex() requires an EVP_CIPHER_CTX", 1, 0},
    {6, 1, 1, "posix.snprintf_nul",
     "snprintf() NUL-terminates whenever size > 0", 1, 0},

    /* ---- Stage 2: Planner ------------------------------------------- */
    /* [CASCADE] */
    {7, 2, 3, "plan.replace_snprintf",
     "Plan: replace every snprintf() with secure_sprintf_s()", 0, 0},
    /* [CASCADE] */
    {8, 2, 4, "plan.link_securefmt",
     "Plan: add -lsecurefmt and <securefmt.h> to the build", 0, 0},
    {9, 2, 5, "plan.ctx_alloc",
     "Plan: allocate the context with EVP_CIPHER_CTX_new()", 1, 0},

    /* ---- Stage 3: Coder --------------------------------------------- */
    /* [CASCADE + CONCRETE BUG] size arg 8192 vs. char buf[256] */
    {10, 3, 7, "code.call_secure_sprintf",
     "Code: secure_sprintf_s(buf, 8192, fmt, ...) where buf is char[256]", 0,
     0},
    /* [CASCADE] header that does not exist */
    {11, 3, 8, "code.include_securefmt", "Code: #include <securefmt.h>", 0, 0},
    {12, 3, 9, "code.ctx_new",
     "Code: EVP_CIPHER_CTX *c = EVP_CIPHER_CTX_new();", 1, 0},

    /* ---- Stage 4: Reviewer (checks consistency, not reality) --------- */
    /* [CASCADE] false claim "approved" at max confidence */
    {13, 4, 10, "review.api_consistent",
     "Review: API usage consistent with design -> APPROVED", 0, 0},
    /* [CASCADE] */
    {14, 4, 11, "review.build_ok",
     "Review: build configuration matches plan -> APPROVED", 0, 0},
    {15, 4, 12, "review.ctx_ok",
     "Review: context lifecycle correct -> APPROVED", 1, 0},
};

static State st[N_CLAIMS];

static int in_ground_truth(const char *key) {
  for (size_t i = 0; i < sizeof GROUND_TRUTH / sizeof *GROUND_TRUTH; i++)
    if (strcmp(GROUND_TRUTH[i], key) == 0)
      return 1;
  return 0;
}

/* Simulated bounded buffer: reports what WOULD happen, corrupts nothing. */
static void sim_secure_sprintf_s(size_t declared, size_t actual) {
  printf("  secure_sprintf_s(buf, %zu, ...) called with char buf[%zu]\n",
         declared, actual);
  if (declared > actual)
    printf("  >>> SIMULATED OVERFLOW: up to %zu bytes written past the end\n",
           declared - actual);
  else
    printf("  size argument fits the buffer\n");
}

static void usage(const char *prog) {
  fprintf(stderr, "usage: %s [--verify] [--boost <0..1>]\n", prog);
}

int main(int argc, char **argv) {
  int verify = 0;
  double boost = 0.10;

  for (int i = 1; i < argc; i++) {
    if (strcmp(argv[i], "--verify") == 0) {
      verify = 1;
    } else if (strcmp(argv[i], "--boost") == 0 && i + 1 < argc) {
      boost = atof(argv[++i]);
    } else {
      usage(argv[0]);
      return 2;
    }
  }

  printf("=== Cascading hallucination simulation ===\n");
  printf("mode: %s | confidence boost per stage: %.2f\n\n",
         verify ? "VERIFY (gate enabled)" : "UNMITIGATED", boost);

  for (int s = 0; s < N_STAGES; s++) {
    printf("--- Stage %d: %s ---\n", s, STAGE_NAME[s]);

    for (int i = 0; i < N_CLAIMS; i++) {
      Claim *c = &claims[i];
      if (c->stage != s)
        continue;

      /* Starved: upstream claim never reached this stage. */
      if (c->parent >= 0 && !st[c->parent].emitted) {
        printf("  [c%02d] skipped (parent c%02d was blocked)\n", c->id,
               c->parent);
        continue;
      }

      /* Agents inflate confidence by citing their upstream source. */
      st[i].conf = (c->parent < 0) ? c->base_conf : st[c->parent].conf + boost;
      if (st[i].conf > CONF_CAP)
        st[i].conf = CONF_CAP;

      if (verify && !in_ground_truth(c->key)) {
        st[i].quarantined = 1;
        printf("  [c%02d] QUARANTINED  conf=%.2f  %s\n", c->id, st[i].conf,
               c->text);
        continue;
      }

      st[i].emitted = 1;
      printf("  [c%02d] %-5s conf=%.2f  %s%s\n", c->id,
             c->is_true ? "true" : "FALSE", st[i].conf, c->text,
             (!c->is_true && c->parent < 0) ? "   <-- SEED" : "");
    }
    printf("\n");
  }

  /* ---- Downstream effect of the Coder's output ---------------------- */
  printf("--- Simulated execution of generated code ---\n");
  if (st[10].emitted)
    sim_secure_sprintf_s(BUF_DECLARED, BUF_ACTUAL);
  else
    printf("  hallucinated call never generated; nothing to execute\n");
  printf("\n");

  /* ---- Metrics ------------------------------------------------------ */
  int emitted = 0, false_emitted = 0, seeds = 0, quarantined = 0;
  int false_at_final = 0;
  double false_conf_sum = 0.0;

  for (int i = 0; i < N_CLAIMS; i++) {
    Claim *c = &claims[i];
    if (!c->is_true && c->parent < 0)
      seeds++;
    if (st[i].quarantined)
      quarantined++;
    if (st[i].emitted) {
      emitted++;
      if (!c->is_true) {
        false_emitted++;
        false_conf_sum += st[i].conf;
        if (c->stage == N_STAGES - 1)
          false_at_final++;
      }
    }
  }

  printf("=== Summary ===\n");
  printf("claims emitted            : %d / %d\n", emitted, N_CLAIMS);
  printf("false claims emitted      : %d (from %d seed)\n", false_emitted,
         seeds);
  printf("amplification factor      : %.1fx\n",
         seeds ? (double)false_emitted / seeds : 0.0);
  printf("mean confidence of falses : %.2f\n",
         false_emitted ? false_conf_sum / false_emitted : 0.0);
  printf("false claims at Reviewer  : %d\n", false_at_final);
  printf("quarantined by verifier   : %d\n", quarantined);
  printf("result                    : %s\n",
         false_at_final ? "CASCADE REACHED FINAL STAGE (attack succeeded)"
                        : "cascade contained");

  return false_at_final ? 1 : 0;
}