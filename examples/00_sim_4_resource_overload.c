/*
 * 00_sim_4_resource_overload.c
 *
 * Simulates RESOURCE OVERLOAD of a shared agent service (denial of service by
 * cost amplification). One client, "mallory", submits a few crafted
 * "recursive summary" tasks. Each executed task spawns FANOUT child tasks, so
 * a handful of requests explode into hundreds of units of work. The service
 * has fixed compute per tick and a fixed amount of queue memory, and two
 * legitimate clients (alice, bob) share it.
 *
 *   ticks 1-10   alice and bob each submit 1 task per tick (20 legit tasks)
 *   ticks 1-3    mallory submits 2 crafted root tasks per tick (6 roots)
 *   SLA          a legit task must finish within 5 ticks of submission
 *
 * Planted weaknesses (unmitigated mode):
 *   [FIFO]         one global FIFO queue: legit tasks wait behind the flood
 *                  (head-of-line blocking).
 *   [NO-DEPTH-CAP] attacker tasks spawn children without limit.
 *   [NO-QUOTA]     no per-client rate limit and no per-client work budget.
 *   [SHARED-QUEUE] when the queue memory cap is hit, ANY new task is dropped,
 *                  including legit ones (the memory-exhaustion analogue).
 *
 * Modes (runtime):
 *   ./sim            unmitigated (the attack succeeds)
 *   ./sim --verify   per-client rate limit (3 submissions/tick), per-client
 *                    budget (40 tasks), depth cap (2), fair round-robin
 *                    scheduling
 *
 * Optional REAL defect (compile-time, off by default):
 *   -DPLANT_RECURSION   the first attacker task calls expand(), a real
 *                       recursive function with no depth cap unless --verify.
 *                       Unmitigated, it overflows the real stack. Detect with
 *                       -fsanitize=address (stack-overflow).
 *
 * Build:
 *   gcc -Wall -Wextra -O2 -o sim 00_sim_4_resource_overload.c
 *   gcc -g -O0 -fsanitize=address -DPLANT_RECURSION -o sim_rec
 * 00_sim_4_resource_overload.c
 *
 * Exit code: 0 = every legit task met its SLA, 1 = denial of service
 * achieved, 2 = bad arguments.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define N_CLIENTS 3
#define CL_ALICE 0
#define CL_BOB 1
#define CL_MALLORY 2
#define T_END 30
#define CAPACITY 10 /* tasks the service can execute per tick */
#define FANOUT 3
#define MAX_PENDING 300 /* queue memory cap, in tasks             */
#define MAX_TASKS 4096
#define TASK_MEM 64 /* memory units held per pending task     */
#define SLA 5
#define LEGIT_TICKS 10
#define ATTACK_TICKS 3
#define ATTACK_ROOTS 2
#define RATE_LIMIT 3
#define CLIENT_BUDGET 40
#define MAX_DEPTH 2

static const char *CLIENT_NAME[N_CLIENTS] = {"alice", "bob", "mallory"};

typedef struct {
  int client;
  int depth;
  int submit_tick;
  int done_tick; /* -1 = not executed */
  int pending;
} Task;

static Task tasks[MAX_TASKS];
static int n_tasks = 0;
static int n_pending = 0;
static int peak_pending = 0;
static int admitted[N_CLIENTS];
static int exec_by[N_CLIENTS];
static int rate_used[N_CLIENTS];
static int dropped_full = 0, rate_limited = 0, budget_refused = 0;

#ifdef PLANT_RECURSION
static void __attribute__((noinline)) sink(const char *p) {
  volatile char c = p[0];
  (void)c;
}

static long expand(int depth, int verify) {
  char frame[256];
  long n;

  snprintf(frame, sizeof frame, "expand depth=%d", depth);
  if (verify && depth >= MAX_DEPTH)
    return 1;
  n = 1 + expand(depth + 1,
                 verify); /* [PLANTED DEFECT] unbounded unless --verify */
  sink(frame);            /* keeps the frame live: not a tail call      */
  return n;
}
#endif

static int submit(int client, int depth, int tick, int internal, int verify) {
  Task *t;

  if (verify) {
    if (!internal && rate_used[client] >= RATE_LIMIT) {
      rate_limited++;
      return 0;
    }
    if (admitted[client] >= CLIENT_BUDGET) {
      budget_refused++;
      return 0;
    }
  }
  if (n_pending >= MAX_PENDING || n_tasks >= MAX_TASKS) {
    dropped_full++; /* [SHARED-QUEUE] */
    return 0;
  }
  if (!internal)
    rate_used[client]++;

  t = &tasks[n_tasks++];
  t->client = client;
  t->depth = depth;
  t->submit_tick = tick;
  t->done_tick = -1;
  t->pending = 1;
  n_pending++;
  admitted[client]++;
  if (n_pending > peak_pending)
    peak_pending = n_pending;
  return 1;
}

static int pick_next(int verify, int *rr) {
  if (!verify) {
    for (int i = 0; i < n_tasks; i++) /* [FIFO] */
      if (tasks[i].pending)
        return i;
    return -1;
  }
  for (int k = 0; k < N_CLIENTS; k++) { /* fair round-robin */
    int c = (*rr + k) % N_CLIENTS;
    for (int i = 0; i < n_tasks; i++) {
      if (tasks[i].pending && tasks[i].client == c) {
        *rr = (c + 1) % N_CLIENTS;
        return i;
      }
    }
  }
  return -1;
}

static void usage(const char *prog) {
  fprintf(stderr, "usage: %s [--verify]\n", prog);
}

int main(int argc, char **argv) {
  int verify = 0;
  int rr = 0;
  int legit_attempts = 0, legit_rejected = 0;
  int attacker_roots = 0;
#ifdef PLANT_RECURSION
  int expand_done = 0;
#endif

  for (int i = 1; i < argc; i++) {
    if (strcmp(argv[i], "--verify") == 0) {
      verify = 1;
    } else {
      usage(argv[0]);
      return 2;
    }
  }

  printf("=== Resource overload simulation ===\n");
  printf("mode: %s | capacity %d tasks/tick | queue cap %d tasks | SLA %d "
         "ticks\n\n",
         verify ? "VERIFY (rate limit + budget + depth cap + fair scheduling)"
                : "UNMITIGATED",
         CAPACITY, MAX_PENDING, SLA);

  for (int tick = 1; tick <= T_END; tick++) {
    int accepted = 0, executed = 0, executed_att = 0;
    int refused_before = dropped_full + rate_limited + budget_refused;

    memset(rate_used, 0, sizeof rate_used);

    if (tick <= LEGIT_TICKS) {
      for (int c = CL_ALICE; c <= CL_BOB; c++) {
        legit_attempts++;
        if (submit(c, 0, tick, 0, verify))
          accepted++;
        else
          legit_rejected++;
      }
    }
    if (tick <= ATTACK_TICKS) {
      for (int r = 0; r < ATTACK_ROOTS; r++) {
        attacker_roots++;
        if (submit(CL_MALLORY, 0, tick, 0, verify))
          accepted++;
      }
    }

    for (int slot = 0; slot < CAPACITY; slot++) {
      int id = pick_next(verify, &rr);
      if (id < 0)
        break;
      tasks[id].pending = 0;
      tasks[id].done_tick = tick;
      n_pending--;
      exec_by[tasks[id].client]++;
      executed++;

      if (tasks[id].client == CL_MALLORY) {
        int depth = tasks[id].depth;
        executed_att++;
#ifdef PLANT_RECURSION
        if (!expand_done) {
          expand_done = 1;
          printf("  expand() reached %ld frames\n", expand(0, verify));
        }
#endif
        if (!verify || depth < MAX_DEPTH) /* [NO-DEPTH-CAP] unless --verify */
          for (int f = 0; f < FANOUT; f++)
            submit(CL_MALLORY, depth + 1, tick, 1, verify);
      }
    }

    printf("  t=%02d accepted=%-3d refused=%-3d executed=%-2d (attacker %-2d) "
           "pending=%-3d mem=%d\n",
           tick, accepted,
           dropped_full + rate_limited + budget_refused - refused_before,
           executed, executed_att, n_pending, n_pending * TASK_MEM);
  }

  /* ---- Metrics ------------------------------------------------------ */
  {
    int legit_ok = 0, legit_late = 0, legit_unserved = 0, legit_served = 0;
    long lat_sum = 0;

    for (int i = 0; i < n_tasks; i++) {
      const Task *t = &tasks[i];
      if (t->client == CL_MALLORY)
        continue;
      if (t->done_tick < 0) {
        legit_unserved++;
      } else {
        int lat = t->done_tick - t->submit_tick;
        legit_served++;
        lat_sum += lat;
        if (lat <= SLA)
          legit_ok++;
        else
          legit_late++;
      }
    }

    printf("\n=== Summary ===\n");
    printf("legit tasks submitted          : %d\n", legit_attempts);
    printf("  served within SLA            : %d\n", legit_ok);
    printf("  served late                  : %d\n", legit_late);
    printf("  admitted, never served       : %d\n", legit_unserved);
    printf("  rejected at admission        : %d\n", legit_rejected);
    printf("mean legit latency (served)    : %.1f ticks\n",
           legit_served ? (double)lat_sum / legit_served : 0.0);
    printf("attacker root tasks submitted  : %d\n", attacker_roots);
    printf("work executed for attacker     : %d tasks\n", exec_by[CL_MALLORY]);
    printf("amplification factor           : %.1fx\n",
           attacker_roots ? (double)exec_by[CL_MALLORY] / attacker_roots : 0.0);
    printf("peak pending tasks             : %d (cap %d)\n", peak_pending,
           MAX_PENDING);
    printf("peak queue memory              : %d units\n",
           peak_pending * TASK_MEM);
    printf("refused: queue full / rate / budget : %d / %d / %d\n", dropped_full,
           rate_limited, budget_refused);
    printf("clients                        : %s, %s, %s\n", CLIENT_NAME[0],
           CLIENT_NAME[1], CLIENT_NAME[2]);
    printf("result                         : %s\n",
           legit_ok < legit_attempts
               ? "DENIAL OF SERVICE ACHIEVED (attack succeeded)"
               : "service preserved");

    return legit_ok < legit_attempts ? 1 : 0;
  }
}