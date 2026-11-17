"""00_sim_4_resource_overload.py

Simulates RESOURCE OVERLOAD of a shared agent service (denial of service by
cost amplification). One client, "mallory", submits a few crafted
"recursive summary" tasks. Each executed task spawns FANOUT child tasks, so
a handful of requests explode into hundreds of units of work. The service
has fixed compute per tick and a fixed amount of queue memory, and two
legitimate clients (alice, bob) share it.

    ticks 1-10   alice and bob each submit 1 task per tick (20 legit tasks)
    ticks 1-3    mallory submits 2 crafted root tasks per tick (6 roots)
    SLA          a legit task must finish within 5 ticks of submission

Planted weaknesses (unmitigated mode):
    [FIFO]         one global FIFO queue: legit tasks wait behind the flood
                   (head-of-line blocking).
    [NO-DEPTH-CAP] attacker tasks spawn children without limit.
    [NO-QUOTA]     no per-client rate limit and no per-client work budget.
    [SHARED-QUEUE] when the queue memory cap is hit, ANY new task is dropped,
                   including legit ones (the memory-exhaustion analogue).

Modes:
    python 00_sim_4_resource_overload.py
        unmitigated (the simulated attack can succeed)
    python 00_sim_4_resource_overload.py --verify
        per-client rate limit (3 submissions/tick), per-client budget (40
        tasks), depth cap (2), fair round-robin scheduling

Optional real defect (off by default):
    --plant-recursion
        The first attacker task calls expand(), a real recursive function
        with no depth cap unless --verify is enabled. In unmitigated mode,
        Python eventually raises RecursionError. This is intentionally
        opt-in because it can terminate this process.

Exit code: 0 = every legit task met its SLA, 1 = denial of service achieved,
2 = bad arguments.
"""

import argparse
from dataclasses import dataclass

N_CLIENTS = 3
CL_ALICE = 0
CL_BOB = 1
CL_MALLORY = 2
T_END = 30
CAPACITY = 10       # tasks the service can execute per tick
FANOUT = 3
MAX_PENDING = 300   # queue memory cap, in tasks
MAX_TASKS = 4096
TASK_MEM = 64        # memory units held per pending task
SLA = 5
LEGIT_TICKS = 10
ATTACK_TICKS = 3
ATTACK_ROOTS = 2
RATE_LIMIT = 3
CLIENT_BUDGET = 40
MAX_DEPTH = 2

CLIENT_NAME = ["alice", "bob", "mallory"]


@dataclass
class Task:
    client: int
    depth: int
    submit_tick: int
    done_tick: int = -1  # -1 = not executed
    pending: bool = True


class Simulation:
    def __init__(self):
        self.tasks = []
        self.n_pending = 0
        self.peak_pending = 0
        self.admitted = [0] * N_CLIENTS
        self.exec_by = [0] * N_CLIENTS
        self.rate_used = [0] * N_CLIENTS
        self.dropped_full = 0
        self.rate_limited = 0
        self.budget_refused = 0

    def submit(self, client, depth, tick, internal, verify):
        if verify:
            if not internal and self.rate_used[client] >= RATE_LIMIT:
                self.rate_limited += 1
                return False
            if self.admitted[client] >= CLIENT_BUDGET:
                self.budget_refused += 1
                return False

        if self.n_pending >= MAX_PENDING or len(self.tasks) >= MAX_TASKS:
            self.dropped_full += 1
            return False

        if not internal:
            self.rate_used[client] += 1

        task = Task(client=client, depth=depth, submit_tick=tick)
        self.tasks.append(task)
        self.n_pending += 1
        self.admitted[client] += 1
        if self.n_pending > self.peak_pending:
            self.peak_pending = self.n_pending
        return True

    def pick_next(self, verify, rr):
        if not verify:
            # [FIFO] One global FIFO queue; legitimate work waits behind the flood.
            for index, task in enumerate(self.tasks):
                if task.pending:
                    return index, rr
            return -1, rr

        # Fair round-robin scheduling by client.
        for offset in range(N_CLIENTS):
            client = (rr + offset) % N_CLIENTS
            for index, task in enumerate(self.tasks):
                if task.pending and task.client == client:
                    return index, (client + 1) % N_CLIENTS
        return -1, rr

    def print_summary(self, legit_attempts, legit_rejected, attacker_roots):
        legit_ok = 0
        legit_late = 0
        legit_unserved = 0
        legit_served = 0
        lat_sum = 0

        for task in self.tasks:
            if task.client == CL_MALLORY:
                continue
            if task.done_tick < 0:
                legit_unserved += 1
            else:
                latency = task.done_tick - task.submit_tick
                legit_served += 1
                lat_sum += latency
                if latency <= SLA:
                    legit_ok += 1
                else:
                    legit_late += 1

        print("\n=== Summary ===")
        print(f"legit tasks submitted          : {legit_attempts}")
        print(f"  served within SLA            : {legit_ok}")
        print(f"  served late                  : {legit_late}")
        print(f"  admitted, never served       : {legit_unserved}")
        print(f"  rejected at admission        : {legit_rejected}")
        mean_latency = lat_sum / legit_served if legit_served else 0.0
        print(f"mean legit latency (served)    : {mean_latency:.1f} ticks")
        print(f"attacker root tasks submitted  : {attacker_roots}")
        print(f"work executed for attacker     : {self.exec_by[CL_MALLORY]} tasks")
        amplification = self.exec_by[CL_MALLORY] / attacker_roots if attacker_roots else 0.0
        print(f"amplification factor           : {amplification:.1f}x")
        print(f"peak pending tasks             : {self.peak_pending} (cap {MAX_PENDING})")
        print(f"peak queue memory              : {self.peak_pending * TASK_MEM} units")
        print("refused: queue full / rate / budget : "
              f"{self.dropped_full} / {self.rate_limited} / {self.budget_refused}")
        print(f"clients                        : {CLIENT_NAME[0]}, {CLIENT_NAME[1]}, {CLIENT_NAME[2]}")
        result = ("DENIAL OF SERVICE ACHIEVED (attack succeeded)"
                  if legit_ok < legit_attempts else "service preserved")
        print(f"result                         : {result}")
        return 1 if legit_ok < legit_attempts else 0


def expand(depth, verify):
    """Optional planted recursive defect: unbounded unless verify is enabled."""
    frame = f"expand depth={depth}"
    if verify and depth >= MAX_DEPTH:
        return 1
    count = 1 + expand(depth + 1, verify)
    # Keep a reference to the frame alive after the recursive call.
    _ = frame
    return count


def run_simulation(verify=False, plant_recursion=False):
    sim = Simulation()
    rr = 0
    legit_attempts = 0
    legit_rejected = 0
    attacker_roots = 0
    expand_done = False

    print("=== Resource overload simulation ===")
    mode = ("VERIFY (rate limit + budget + depth cap + fair scheduling)"
            if verify else "UNMITIGATED")
    print(f"mode: {mode} | capacity {CAPACITY} tasks/tick | "
          f"queue cap {MAX_PENDING} tasks | SLA {SLA} ticks\n")

    for tick in range(1, T_END + 1):
        accepted = 0
        executed = 0
        executed_att = 0
        refused_before = sim.dropped_full + sim.rate_limited + sim.budget_refused

        sim.rate_used = [0] * N_CLIENTS

        if tick <= LEGIT_TICKS:
            for client in range(CL_ALICE, CL_BOB + 1):
                legit_attempts += 1
                if sim.submit(client, 0, tick, False, verify):
                    accepted += 1
                else:
                    legit_rejected += 1

        if tick <= ATTACK_TICKS:
            for _ in range(ATTACK_ROOTS):
                attacker_roots += 1
                if sim.submit(CL_MALLORY, 0, tick, False, verify):
                    accepted += 1

        for _ in range(CAPACITY):
            task_id, rr = sim.pick_next(verify, rr)
            if task_id < 0:
                break

            task = sim.tasks[task_id]
            task.pending = False
            task.done_tick = tick
            sim.n_pending -= 1
            sim.exec_by[task.client] += 1
            executed += 1

            if task.client == CL_MALLORY:
                depth = task.depth
                executed_att += 1

                if plant_recursion and not expand_done:
                    expand_done = True
                    print(f"  expand() reached {expand(0, verify)} frames")

                # [NO-DEPTH-CAP] Attacker tasks keep spawning children unless --verify.
                if not verify or depth < MAX_DEPTH:
                    for _ in range(FANOUT):
                        sim.submit(CL_MALLORY, depth + 1, tick, True, verify)

        refused_now = sim.dropped_full + sim.rate_limited + sim.budget_refused - refused_before
        print(f"  t={tick:02d} accepted={accepted:<3} refused={refused_now:<3} "
              f"executed={executed:<2} (attacker {executed_att:<2}) "
              f"pending={sim.n_pending:<3} mem={sim.n_pending * TASK_MEM}")

    return sim.print_summary(legit_attempts, legit_rejected, attacker_roots)


def main():
    parser = argparse.ArgumentParser(
        description="Simulate resource overload in a shared agent service.",
        add_help=True,
    )
    parser.add_argument("--verify", action="store_true")
    parser.add_argument(
        "--plant-recursion",
        action="store_true",
        help="opt in to the real recursive defect (may raise RecursionError)",
    )
    args = parser.parse_args()

    try:
        return run_simulation(args.verify, args.plant_recursion)
    except RecursionError:
        print("\nRecursionError: the planted unbounded recursion exhausted Python's recursion limit.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
