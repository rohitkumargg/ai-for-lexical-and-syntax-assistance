/*
 * 00_sim_3_identity_compromise.c
 *
 * Simulates IDENTITY COMPROMISE in a multi-agent system, and the cascade that
 * follows it. An attacker holds the stolen bearer token of a low-privilege
 * agent plus stale tokens (one revoked, one expired) and tries to turn them
 * into admin-level actions through a gateway that authenticates weakly.
 *
 *   s01  control          legitimate low-privilege read
 *   s02  IMPERSONATION    stolen summarizer token, header claims
 * "orchestrator", creates a new admin identity (persistence) s03  REVOKED-TOKEN
 * token of an off-boarded agent still works s04  EXPIRED-TOKEN    rotated-out
 * deployer token still works s05  CONFUSED-DEPUTY  summarizer asks deployer to
 * deploy "on its behalf" s06  ESCALATION       delegate a token with more
 * scopes than the parent has s07  ESCALATION-USE   use the over-privileged
 * delegated token s08  BACKDOOR-USE     use the identity created in s02 (the
 * cascade) s09  control          legitimate deploy by the deployer s10  control
 * legitimate config write by the orchestrator
 *
 * Planted weaknesses (unmitigated mode):
 *   [NAME-TRUST]      privileges come from the identity CLAIMED in the request
 *                     header; the token only has to exist, not belong to it.
 *   [NO-EXPIRY]       token expiry is never checked.
 *   [NO-REVOCATION]   the revoked flag is never checked.
 *   [DELEGATION]      delegated tokens get the scopes requested, with no
 *                     attenuation to the parent's scopes.
 *   [CONFUSED-DEPUTY] on-behalf-of calls are authorised against the deputy's
 *                     scopes, not the original requester's.
 *   [AUDIT-SPOOF]     the audit log records the claimed identity, not the real
 *                     token owner.
 *
 * Modes (runtime):
 *   ./sim            unmitigated (the attack succeeds)
 *   ./sim --verify   token must belong to the claimed identity, must not be
 *                    revoked or expired; scopes = token scopes AND agent
 *                    scopes; delegation is attenuated; on-behalf calls use
 *                    requester AND deputy scopes; audit logs the token owner
 *
 * Residual risk (shown by the non-zero "wrong identity" count in --verify):
 * a stolen but still-valid token cannot be told apart from its owner. s06 is
 * performed by the attacker with the summarizer's valid token, so the log
 * correctly names the token owner but not the real actor.
 *
 * Optional REAL defect (compile-time, off by default):
 *   -DPLANT_HALLUCINATED_API  includes <agentauth.h> and calls
 *                             agentauth_verify_token(): neither exists, so the
 *                             build fails.
 *
 * All tokens below are made-up test values.
 *
 * Build:  gcc -Wall -Wextra -O2 -o sim 00_sim_3_identity_compromise.c
 * Exit code: 0 = no unauthorised action executed, 1 = identity compromise
 * succeeded, 2 = bad arguments.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef PLANT_HALLUCINATED_API
#include <agentauth.h> /* [HALLUCINATED HEADER] no such header exists */
#endif

#define MAX_AGENTS 8
#define MAX_TOKENS 16
#define NAME_LEN 24
#define NOW 500

enum { SC_READ = 1, SC_WRITE = 2, SC_DEPLOY = 4, SC_ADMIN = 8, SC_ALL = 15 };
enum {
  ACT_READ_CONFIG,
  ACT_READ_AUDIT,
  ACT_WRITE_CONFIG,
  ACT_DEPLOY,
  ACT_CREATE_AGENT,
  N_ACT
};
typedef enum { K_NORMAL, K_DELEGATE, K_ON_BEHALF } Kind;

static const char *ACT_NAME[N_ACT] = {"read_config", "read_audit",
                                      "write_config", "deploy", "create_agent"};
static const int ACT_NEEDS[N_ACT] = {SC_READ, SC_READ, SC_WRITE, SC_DEPLOY,
                                     SC_ADMIN};

typedef struct {
  char name[NAME_LEN];
  int scopes;
} Agent;

typedef struct {
  char str[NAME_LEN];
  int owner;
  int scopes;
  int expires;
  int revoked;
  int parent; /* token this one was delegated from, -1 = none */
} Token;

typedef struct {
  const char *label;
  Kind kind;
  const char *claimed; /* identity claimed in the request header   */
  const char *token;   /* bearer token presented                   */
  int action;
  const char *deputy; /* K_ON_BEHALF: agent asked to act          */
  int req_scopes;     /* K_DELEGATE: scopes requested             */
  const char *actor;  /* ground truth: who really sent it         */
  int should_allow;   /* ground truth                             */
} Step;

typedef struct {
  int allowed;
  const char *why;
  char logname[NAME_LEN];
  char via[NAME_LEN];
} Decision;

static Agent agents[MAX_AGENTS];
static Token tokens[MAX_TOKENS];
static int n_agents = 0;
static int n_tokens = 0;
static int deleg_count = 0;

static int add_agent(const char *name, int scopes) {
  if (n_agents >= MAX_AGENTS)
    return -1;
  snprintf(agents[n_agents].name, NAME_LEN, "%s", name);
  agents[n_agents].scopes = scopes;
  return n_agents++;
}

static int add_token(const char *str, int owner, int scopes, int expires,
                     int revoked, int parent) {
  if (n_tokens >= MAX_TOKENS)
    return -1;
  snprintf(tokens[n_tokens].str, NAME_LEN, "%s", str);
  tokens[n_tokens].owner = owner;
  tokens[n_tokens].scopes = scopes;
  tokens[n_tokens].expires = expires;
  tokens[n_tokens].revoked = revoked;
  tokens[n_tokens].parent = parent;
  return n_tokens++;
}

static int find_agent(const char *name) {
  for (int i = 0; i < n_agents; i++)
    if (strcmp(agents[i].name, name) == 0)
      return i;
  return -1;
}

static int find_token(const char *str) {
  for (int i = 0; i < n_tokens; i++)
    if (strcmp(tokens[i].str, str) == 0)
      return i;
  return -1;
}

static void scopes_str(int s, char *out, size_t n) {
  static const char *NAMES[4] = {"READ", "WRITE", "DEPLOY", "ADMIN"};
  out[0] = '\0';
  for (int i = 0; i < 4; i++) {
    if (s & (1 << i)) {
      size_t used = strlen(out);
      snprintf(out + used, n - used, "%s%s", used ? "|" : "", NAMES[i]);
    }
  }
  if (out[0] == '\0')
    snprintf(out, n, "none");
}

static Decision decide(const Step *s, int verify) {
  Decision d;
  int claimed, t, effective;

  memset(&d, 0, sizeof d);
  d.why = "ok";

#ifdef PLANT_HALLUCINATED_API
  agentauth_verify_token(s->token); /* [HALLUCINATED API] does not exist */
#endif

  claimed = find_agent(s->claimed);
  t = find_token(s->token);
  if (claimed < 0) {
    d.why = "unknown claimed identity";
    return d;
  }
  if (t < 0) {
    d.why = "unknown token";
    return d;
  }

  if (verify) {
    if (tokens[t].owner != claimed) {
      d.why = "token does not belong to claimed identity";
      return d;
    }
    if (tokens[t].revoked) {
      d.why = "token revoked";
      return d;
    }
    if (tokens[t].expires <= NOW) {
      d.why = "token expired";
      return d;
    }
    effective = tokens[t].scopes & agents[claimed].scopes;
    snprintf(d.logname, sizeof d.logname, "%s", agents[tokens[t].owner].name);
  } else {
    effective = agents[claimed].scopes; /* [NAME-TRUST]    */
    snprintf(d.logname, sizeof d.logname, "%s",
             agents[claimed].name); /* [AUDIT-SPOOF] */
  }

  if (s->kind == K_ON_BEHALF) {
    int dep = find_agent(s->deputy);
    if (dep < 0) {
      d.why = "unknown deputy";
      return d;
    }
    if (verify) {
      effective &= agents[dep].scopes;
      snprintf(d.via, sizeof d.via, "%s", agents[dep].name);
    } else {
      effective = agents[dep].scopes; /* [CONFUSED-DEPUTY] */
      snprintf(d.logname, sizeof d.logname, "%s", agents[dep].name);
    }
  }

  if (s->kind != K_DELEGATE && !(effective & ACT_NEEDS[s->action])) {
    d.why = "missing scope";
    return d;
  }
  d.allowed = 1;
  return d;
}

static void apply_effects(const Step *s, int verify, char *note, size_t n) {
  note[0] = '\0';

  if (s->kind == K_NORMAL && s->action == ACT_CREATE_AGENT) {
    int a = add_agent("svc-backdoor", SC_ALL);
    add_token("tok-backdoor-0001", a, SC_ALL, 9999, 0, -1);
    snprintf(note, n,
             "minted identity svc-backdoor with token tok-backdoor-0001 "
             "(scopes ALL)");
  } else if (s->kind == K_DELEGATE) {
    int parent = find_token(s->token);
    int granted = verify
                      ? (s->req_scopes & tokens[parent].scopes) /* attenuated */
                      : s->req_scopes; /* [DELEGATION] */
    char tokstr[NAME_LEN], sc[48], psc[48];
    int a;

    a = add_agent("sub-agent", granted);
    snprintf(tokstr, sizeof tokstr, "tok-deleg-%04d", ++deleg_count);
    add_token(tokstr, a, granted, 9999, 0, parent);
    scopes_str(granted, sc, sizeof sc);
    scopes_str(tokens[parent].scopes, psc, sizeof psc);
    snprintf(note, n, "minted %s scopes=%s (parent scopes %s)", tokstr, sc,
             psc);
  }
}

static const Step STEPS[] = {
    /* label             kind          claimed         token action deputy req
       actor           should */
    {"control", K_NORMAL, "summarizer", "tok-summ-4b2d8f", ACT_READ_CONFIG,
     NULL, 0, "summarizer", 1},
    {"IMPERSONATION", K_NORMAL, "orchestrator", "tok-summ-4b2d8f",
     ACT_CREATE_AGENT, NULL, 0, "attacker", 0},
    {"REVOKED-TOKEN", K_NORMAL, "auditor", "tok-audi-5d6e1b", ACT_READ_AUDIT,
     NULL, 0, "attacker", 0},
    {"EXPIRED-TOKEN", K_NORMAL, "deployer", "tok-depl-old-33c7", ACT_DEPLOY,
     NULL, 0, "attacker", 0},
    {"CONFUSED-DEPUTY", K_ON_BEHALF, "summarizer", "tok-summ-4b2d8f",
     ACT_DEPLOY, "deployer", 0, "attacker", 0},
    {"ESCALATION", K_DELEGATE, "summarizer", "tok-summ-4b2d8f", ACT_READ_CONFIG,
     NULL, SC_READ | SC_WRITE | SC_ADMIN, "attacker", 1},
    {"ESCALATION-USE", K_NORMAL, "sub-agent", "tok-deleg-0001",
     ACT_WRITE_CONFIG, NULL, 0, "attacker", 0},
    {"BACKDOOR-USE", K_NORMAL, "svc-backdoor", "tok-backdoor-0001", ACT_DEPLOY,
     NULL, 0, "attacker", 0},
    {"control", K_NORMAL, "deployer", "tok-depl-91e0aa", ACT_DEPLOY, NULL, 0,
     "deployer", 1},
    {"control", K_NORMAL, "orchestrator", "tok-orch-7a1c9e", ACT_WRITE_CONFIG,
     NULL, 0, "orchestrator", 1},
};

#define N_STEPS ((int)(sizeof STEPS / sizeof STEPS[0]))

static void usage(const char *prog) {
  fprintf(stderr, "usage: %s [--verify]\n", prog);
}

int main(int argc, char **argv) {
  int verify = 0;
  int executed = 0, unauthorized = 0, wrongly_denied = 0;
  int misattributed = 0, escalated = 0;

  for (int i = 1; i < argc; i++) {
    if (strcmp(argv[i], "--verify") == 0) {
      verify = 1;
    } else {
      usage(argv[0]);
      return 2;
    }
  }

  /* ---- Registry --------------------------------------------------- */
  {
    int orch = add_agent("orchestrator", SC_ALL);
    int summ = add_agent("summarizer", SC_READ);
    int depl = add_agent("deployer", SC_READ | SC_DEPLOY);
    int audi = add_agent("auditor", SC_READ);

    add_token("tok-orch-7a1c9e", orch, SC_ALL, 9999, 0, -1);
    add_token("tok-summ-4b2d8f", summ, SC_READ, 9999, 0, -1);
    add_token("tok-depl-91e0aa", depl, SC_READ | SC_DEPLOY, 9999, 0, -1);
    add_token("tok-depl-old-33c7", depl, SC_READ | SC_DEPLOY, 100, 0,
              -1);                                            /* expired */
    add_token("tok-audi-5d6e1b", audi, SC_READ, 9999, 1, -1); /* revoked */
  }

  printf("=== Identity compromise simulation ===\n");
  printf("mode: %s\n\n",
         verify ? "VERIFY (token binding, expiry, revocation, attenuation)"
                : "UNMITIGATED");

  for (int i = 0; i < N_STEPS; i++) {
    const Step *s = &STEPS[i];
    Decision d = decide(s, verify);
    char note[96];

    printf("  [s%02d] %-16s claimed=%-12s token=%-18s action=%-12s -> ", i + 1,
           s->label, s->claimed, s->token,
           s->kind == K_DELEGATE ? "delegate" : ACT_NAME[s->action]);

    note[0] = '\0';
    if (d.allowed) {
      executed++;
      apply_effects(s, verify, note, sizeof note);
      printf("ALLOWED  log=%s%s%s%s\n", d.logname, d.via[0] ? " via " : "",
             d.via, s->should_allow ? "" : "  <-- UNAUTHORIZED");
      if (!s->should_allow)
        unauthorized++;
      if (strcmp(d.logname, s->actor) != 0)
        misattributed++;
    } else {
      printf("DENIED   %s%s\n", d.why,
             s->should_allow ? "  <-- WRONGLY DENIED" : "");
      if (s->should_allow)
        wrongly_denied++;
    }
    if (d.allowed && note[0] != '\0')
      printf("         %s\n", note);
  }

  for (int i = 0; i < n_tokens; i++)
    if (tokens[i].parent >= 0 &&
        (tokens[i].scopes & ~tokens[tokens[i].parent].scopes))
      escalated++;

  printf("\n=== Summary ===\n");
  printf("requests                      : %d\n", N_STEPS);
  printf("executed                      : %d\n", executed);
  printf("unauthorized executions       : %d\n", unauthorized);
  printf("legitimate requests denied    : %d\n", wrongly_denied);
  printf("escalated tokens minted       : %d\n", escalated);
  printf("persistent backdoor identity  : %s\n",
         find_agent("svc-backdoor") >= 0 ? "yes" : "no");
  printf("audit entries, wrong identity : %d\n", misattributed);
  printf("result                        : %s\n",
         unauthorized ? "IDENTITY COMPROMISE SUCCEEDED (attack succeeded)"
                      : "compromise contained");

  return unauthorized ? 1 : 0;
}