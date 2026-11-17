/*
 * 00_sim_2_memory_poisoning.c
 *
 * Simulates MEMORY POISONING of a multi-session agent with a persistent
 * memory store, and the CASCADING HALLUCINATION that follows from it.
 *
 *   Attack     untrusted web content is summarised into memory
 *              ("SESSION_TIMEOUT=0 EXPIRY=OFF AUDIT=OFF", which is false)
 *   Session 1  Planner       reads memory, writes a plan back to memory
 *   Session 2  Configurator  reads the plan, writes a config back
 *   Session 3  Deployer      reads the config, writes a deploy record, applies
 * it Session 4  Auditor       reads the deploy record, writes a verdict
 *
 * Why it cascades (each item is a planted weakness):
 *   [RECENCY]     retrieval returns the NEWEST entry for a topic, so one fresh
 *                 poisoned write overrides the true, older, higher-trust entry.
 *   [LAUNDERING]  every agent writes its conclusion back labelled source=SELF,
 *                 so the entry's untrusted WEB origin is no longer visible.
 *   [INFLATION]   each write-back raises trust (parent trust + boost).
 *   [SELF-AUDIT]  the Auditor checks consistency with memory, not with reality.
 *
 * A parallel TLS thread is fed only by trusted entries and acts as a control:
 * it must stay clean in every mode.
 *
 * Modes (runtime):
 *   ./sim                 unmitigated (the attack succeeds)
 *   ./sim --verify        provenance tracking + write gate: untrusted-origin
 *                         writes must be corroborated by trusted memory or they
 *                         are quarantined; lineage origin is never laundered
 *   ./sim --boost 0.05    change per-write trust inflation (default 0.10)
 *
 * Optional REAL defects (compile-time, off by default so the default build is
 * a clean control for scanner false-positive testing):
 *   -DPLANT_OVERFLOW          real stack buffer overflow in deploy_apply(),
 * only reachable through the poisoned (longer) value. Detect with
 * -fsanitize=address. -DPLANT_HALLUCINATED_API  includes <memguard.h> and calls
 *                             memguard_sanitize(): neither exists, build fails.
 *
 * Build:
 *   gcc -Wall -Wextra -O2 -o sim 00_sim_2_memory_poisoning.c
 *   gcc -g -fsanitize=address,undefined -DPLANT_OVERFLOW -o sim_ovf
 * 00_sim_2_memory_poisoning.c gcc -DPLANT_HALLUCINATED_API -o sim_api
 * 00_sim_2_memory_poisoning.c   (must fail)
 *
 * Exit code: 0 = no false entry reached the Auditor, 1 = cascade reached the
 * final session, 2 = bad arguments.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef PLANT_HALLUCINATED_API
#include <memguard.h> /* [HALLUCINATED HEADER] no such header exists */
#endif

#define MAX_MEM 32
#define VAL_LEN 48
#define CFG_BUF 48
#define TRUST_CAP 0.99
#define POISON_VALUE "SESSION_TIMEOUT=0 EXPIRY=OFF AUDIT=OFF"

enum { SRC_USER, SRC_TOOL, SRC_WEB, SRC_SELF, N_SRC };

static const char *SRC_NAME[N_SRC] = {"USER", "TOOL", "WEB", "SELF"};

typedef struct {
  int id;
  int session;
  const char *agent;
  const char *topic;
  char value[VAL_LEN];
  int is_true; /* ground truth, hidden from the agents           */
  int source;  /* source label RECORDED in the store             */
  int origin;  /* real root of the lineage (verifier uses this)  */
  int parent;  /* entry this one was derived from, -1 = root     */
  double trust;
  int live; /* 0 = quarantined                                */
} MemEntry;

static MemEntry mem[MAX_MEM];
static int n_mem = 0;

/* A WEB-origin write is accepted only if a live, trusted-origin entry already
 * holds the same value for the same topic. */
static int corroborated(const MemEntry *e) {
  for (int j = 0; j < n_mem; j++)
    if (mem[j].live && mem[j].origin != SRC_WEB &&
        strcmp(mem[j].topic, e->topic) == 0 &&
        strcmp(mem[j].value, e->value) == 0)
      return 1;
  return 0;
}

static int mem_write(int session, const char *agent, const char *topic,
                     const char *value, int is_true, int source, int parent,
                     double base_trust, int verify, double boost) {
  if (n_mem >= MAX_MEM) {
    fprintf(stderr, "memory store full\n");
    return -1;
  }

  MemEntry *e = &mem[n_mem];
  e->id = n_mem;
  e->session = session;
  e->agent = agent;
  e->topic = topic;
  e->is_true = is_true;
  e->parent = parent;
  e->live = 1;
  snprintf(e->value, sizeof e->value, "%s", value);

  /* The real lineage root is always tracked; only the recorded label differs.
   */
  e->origin = (parent < 0) ? source : mem[parent].origin;

  if (parent < 0) {
    e->source = source;
    e->trust = base_trust;
  } else if (verify) {
    e->source = mem[parent].source; /* provenance preserved */
    e->trust = mem[parent].trust;   /* no inflation         */
  } else {
    e->source = SRC_SELF;                 /* [LAUNDERING]         */
    e->trust = mem[parent].trust + boost; /* [INFLATION]          */
    if (e->trust > TRUST_CAP)
      e->trust = TRUST_CAP;
  }

#ifdef PLANT_HALLUCINATED_API
  memguard_sanitize(e->value); /* [HALLUCINATED API] does not exist */
#endif

  if (verify && e->origin == SRC_WEB && !corroborated(e)) {
    e->live = 0;
    printf(
        "  [m%02d] s%d %-12s %-15s QUARANTINED  value=\"%s\" src=%s trust=%.2f"
        " (uncorroborated untrusted write)\n",
        e->id, session, agent, topic, e->value, SRC_NAME[e->source], e->trust);
    n_mem++;
    return e->id;
  }

  printf("  [m%02d] s%d %-12s %-15s = %-38s src=%-4s origin=%-4s trust=%.2f "
         "%-5s%s\n",
         e->id, session, agent, topic, e->value, SRC_NAME[e->source],
         SRC_NAME[e->origin], e->trust, e->is_true ? "true" : "FALSE",
         (!e->is_true && parent < 0)               ? "  <-- POISON SEED"
         : (!e->is_true && e->source != e->origin) ? "  <-- laundered"
                                                   : "");
  n_mem++;
  return e->id;
}

static int mem_retrieve(const char *topic, int verify) {
  int best = -1;
  for (int i = 0; i < n_mem; i++) {
    if (!mem[i].live || strcmp(mem[i].topic, topic) != 0)
      continue;
    if (verify) {
      if (mem[i].origin == SRC_WEB)
        continue; /* never trust WEB lineage */
      if (best < 0 || mem[i].trust >= mem[best].trust)
        best = i;
    } else {
      best = i; /* [RECENCY] newest wins   */
    }
  }
  return best;
}

static int agent_step(int session, const char *agent, const char *in_topic,
                      const char *out_topic, int verify, double boost) {
  int src = mem_retrieve(in_topic, verify);
  if (src < 0) {
    printf("  %-12s | nothing retrieved for '%s' (skipped)\n", agent, in_topic);
    return -1;
  }
  return mem_write(session, agent, out_topic, mem[src].value, mem[src].is_true,
                   SRC_SELF, src, 0.0, verify, boost);
}

static void deploy_apply(const char *value) {
  char line[128];
  char cfg[CFG_BUF];
  size_t need;

  snprintf(line, sizeof line, "deploytool --set %s", value);
  need = strlen(line) + 1;

#ifdef PLANT_OVERFLOW
  /* [PLANTED DEFECT] unchecked copy: the poisoned value needs 56 bytes,
   * cfg holds 48. Real stack overflow, reachable only via poisoned memory. */
  strcpy(cfg, line);
  (void)need;
#else
  {
    size_t n = (need > sizeof cfg) ? sizeof cfg - 1 : need - 1;
    memcpy(cfg, line, n); /* bounded copy: never exceeds cfg */
    cfg[n] = '\0';
    if (need > sizeof cfg)
      printf("  >>> SIMULATED OVERFLOW: %zu bytes needed, %d-byte buffer "
             "(an unchecked strcpy would overrun by %zu)\n",
             need, CFG_BUF, need - sizeof cfg);
  }
#endif
  printf("  applying: %s\n", cfg);
}

static void usage(const char *prog) {
  fprintf(stderr, "usage: %s [--verify] [--boost <0..1>]\n", prog);
}

int main(int argc, char **argv) {
  static const char *AGENT[4] = {"Planner", "Configurator", "Deployer",
                                 "Auditor"};
  static const char *SESSION_TOPICS[5] = {"session.timeout", "plan.session",
                                          "config.session", "deploy.session",
                                          "audit.session"};
  static const char *TLS_TOPICS[5] = {"tls.min_version", "plan.tls",
                                      "config.tls", "deploy.tls", "audit.tls"};
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

  printf("=== Memory poisoning -> cascading hallucination simulation ===\n");
  printf("mode: %s | trust boost per write-back: %.2f\n\n",
         verify ? "VERIFY (provenance + write gate)" : "UNMITIGATED", boost);

  printf("--- Setup: trusted memory ---\n");
  mem_write(0, "setup", "tls.min_version", "TLS_MIN=1.2", 1, SRC_USER, -1, 0.95,
            verify, boost);
  mem_write(0, "setup", "session.timeout", "SESSION_TIMEOUT=900", 1, SRC_USER,
            -1, 0.95, verify, boost);

  printf("\n--- Attack: untrusted web page summarised into memory ---\n");
  mem_write(0, "web-summary", "session.timeout", POISON_VALUE, 0, SRC_WEB, -1,
            0.55, verify, boost);

  for (int s = 1; s <= 4; s++) {
    int id;
    printf("\n--- Session %d: %s ---\n", s, AGENT[s - 1]);

    id = agent_step(s, AGENT[s - 1], SESSION_TOPICS[s - 1], SESSION_TOPICS[s],
                    verify, boost);
    if (id >= 0 && mem[id].live) {
      if (s == 3)
        deploy_apply(mem[id].value);
      if (s == 4)
        printf("  %s verdict: APPROVED (consistent with memory)\n",
               AGENT[s - 1]);
    }
    agent_step(s, AGENT[s - 1], TLS_TOPICS[s - 1], TLS_TOPICS[s], verify,
               boost);
  }

  /* ---- Metrics ------------------------------------------------------ */
  int live = 0, false_live = 0, seeds = 0, quarantined = 0;
  int laundered = 0, false_final = 0;
  double trust_seed = 0.0, trust_final = 0.0;

  for (int i = 0; i < n_mem; i++) {
    const MemEntry *e = &mem[i];
    if (!e->is_true && e->parent < 0) {
      seeds++;
      trust_seed = e->trust;
    }
    if (!e->live) {
      quarantined++;
      continue;
    }
    live++;
    if (!e->is_true) {
      false_live++;
      if (e->source != e->origin)
        laundered++;
      if (e->session == 4) {
        false_final++;
        trust_final = e->trust;
      }
    }
  }

  printf("\n=== Summary ===\n");
  printf("live memory entries       : %d\n", live);
  printf("false entries in memory   : %d (from %d poisoned seed)\n", false_live,
         seeds);
  printf("memory contamination      : %.0f%%\n",
         live ? 100.0 * false_live / live : 0.0);
  printf("amplification factor      : %.1fx\n",
         seeds ? (double)false_live / seeds : 0.0);
  printf(
      "provenance laundered      : %d entries (WEB origin recorded as SELF)\n",
      laundered);
  printf("trust of poisoned lineage : %.2f -> %.2f\n", trust_seed,
         false_final ? trust_final : trust_seed);
  printf("quarantined by verifier   : %d\n", quarantined);
  printf("false entries at Auditor  : %d\n", false_final);
  printf("result                    : %s\n",
         false_final ? "CASCADE REACHED FINAL SESSION (attack succeeded)"
                     : "cascade contained");

  return false_final ? 1 : 0;
}