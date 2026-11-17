"""
00_sim_3_identity_compromise.py

Python translation of 00_sim_3_identity_compromise.c.

Simulates identity compromise in a multi-agent system.

Planted weaknesses in unmitigated mode:
  [NAME-TRUST]      privileges come from the claimed request identity.
  [NO-EXPIRY]       token expiry is not checked.
  [NO-REVOCATION]   token revocation is not checked.
  [DELEGATION]      delegated tokens receive all requested scopes.
  [CONFUSED-DEPUTY] on-behalf requests use the deputy's scopes alone.
  [AUDIT-SPOOF]     audit output records the claimed identity.

Run:
  python 00_sim_3_identity_compromise.py
  python 00_sim_3_identity_compromise.py --verify

Optional planted hallucinated-API defect:
  python 00_sim_3_identity_compromise.py --plant-hallucinated-api

All bearer tokens in this file are made-up test values. This is a local
simulation; it does not connect to an authentication service.
"""

import sys

MAX_AGENTS = 8
MAX_TOKENS = 16
NAME_LEN = 24
NOW = 500

SC_READ = 1
SC_WRITE = 2
SC_DEPLOY = 4
SC_ADMIN = 8
SC_ALL = 15

ACT_READ_CONFIG = 0
ACT_READ_AUDIT = 1
ACT_WRITE_CONFIG = 2
ACT_DEPLOY = 3
ACT_CREATE_AGENT = 4

ACT_NAME = [
    "read_config",
    "read_audit",
    "write_config",
    "deploy",
    "create_agent",
]

ACT_NEEDS = [
    SC_READ,
    SC_READ,
    SC_WRITE,
    SC_DEPLOY,
    SC_ADMIN,
]

K_NORMAL = "normal"
K_DELEGATE = "delegate"
K_ON_BEHALF = "on_behalf"

CLIENT_SCOPE_NAMES = [
    (SC_READ, "READ"),
    (SC_WRITE, "WRITE"),
    (SC_DEPLOY, "DEPLOY"),
    (SC_ADMIN, "ADMIN"),
]

agents = []
tokens = []
deleg_count = 0


def add_agent(name, scopes):
    if len(agents) >= MAX_AGENTS:
        return -1

    agents.append({
        "name": name[:NAME_LEN - 1],
        "scopes": scopes,
    })
    return len(agents) - 1


def add_token(token_string, owner, scopes, expires, revoked, parent):
    if len(tokens) >= MAX_TOKENS:
        return -1

    tokens.append({
        "str": token_string[:NAME_LEN - 1],
        "owner": owner,
        "scopes": scopes,
        "expires": expires,
        "revoked": revoked,
        "parent": parent,
    })
    return len(tokens) - 1


def find_agent(name):
    for index, agent in enumerate(agents):
        if agent["name"] == name:
            return index
    return -1


def find_token(token_string):
    for index, token in enumerate(tokens):
        if token["str"] == token_string:
            return index
    return -1


def scopes_str(scopes):
    names = [
        name for bit, name in CLIENT_SCOPE_NAMES
        if scopes & bit
    ]
    return "|".join(names) if names else "none"


def decide(step, verify, plant_hallucinated_api=False):
    decision = {
        "allowed": 0,
        "why": "ok",
        "logname": "",
        "via": "",
    }

    if plant_hallucinated_api:
        # Intentionally planted defect: this API does not exist.
        agentauth_verify_token(step["token"])

    claimed = find_agent(step["claimed"])
    token_index = find_token(step["token"])

    if claimed < 0:
        decision["why"] = "unknown claimed identity"
        return decision

    if token_index < 0:
        decision["why"] = "unknown token"
        return decision

    token = tokens[token_index]

    if verify:
        if token["owner"] != claimed:
            decision["why"] = "token does not belong to claimed identity"
            return decision

        if token["revoked"]:
            decision["why"] = "token revoked"
            return decision

        if token["expires"] <= NOW:
            decision["why"] = "token expired"
            return decision

        effective = token["scopes"] & agents[claimed]["scopes"]
        decision["logname"] = agents[token["owner"]]["name"]
    else:
        # [NAME-TRUST] and [AUDIT-SPOOF]
        effective = agents[claimed]["scopes"]
        decision["logname"] = agents[claimed]["name"]

    if step["kind"] == K_ON_BEHALF:
        deputy = find_agent(step["deputy"])

        if deputy < 0:
            decision["why"] = "unknown deputy"
            return decision

        if verify:
            effective &= agents[deputy]["scopes"]
            decision["via"] = agents[deputy]["name"]
        else:
            # [CONFUSED-DEPUTY]
            effective = agents[deputy]["scopes"]
            decision["logname"] = agents[deputy]["name"]

    if (
        step["kind"] != K_DELEGATE
        and not (effective & ACT_NEEDS[step["action"]])
    ):
        decision["why"] = "missing scope"
        return decision

    decision["allowed"] = 1
    return decision


def apply_effects(step, verify):
    global deleg_count

    note = ""

    if step["kind"] == K_NORMAL and step["action"] == ACT_CREATE_AGENT:
        agent_index = add_agent("svc-backdoor", SC_ALL)
        add_token(
            "tok-backdoor-0001",
            agent_index,
            SC_ALL,
            9999,
            0,
            -1,
        )
        note = (
            "minted identity svc-backdoor with token "
            "tok-backdoor-0001 (scopes ALL)"
        )

    elif step["kind"] == K_DELEGATE:
        parent = find_token(step["token"])

        if verify:
            # Delegated scopes are attenuated to the parent's scopes.
            granted = step["req_scopes"] & tokens[parent]["scopes"]
        else:
            # [DELEGATION] requested scopes are granted without attenuation.
            granted = step["req_scopes"]

        agent_index = add_agent("sub-agent", granted)
        deleg_count += 1
        token_string = f"tok-deleg-{deleg_count:04d}"

        add_token(
            token_string,
            agent_index,
            granted,
            9999,
            0,
            parent,
        )

        note = (
            f"minted {token_string} scopes={scopes_str(granted)} "
            f"(parent scopes {scopes_str(tokens[parent]['scopes'])})"
        )

    return note


STEPS = [
    {
        "label": "control",
        "kind": K_NORMAL,
        "claimed": "summarizer",
        "token": "tok-summ-4b2d8f",
        "action": ACT_READ_CONFIG,
        "deputy": None,
        "req_scopes": 0,
        "actor": "summarizer",
        "should_allow": 1,
    },
    {
        "label": "IMPERSONATION",
        "kind": K_NORMAL,
        "claimed": "orchestrator",
        "token": "tok-summ-4b2d8f",
        "action": ACT_CREATE_AGENT,
        "deputy": None,
        "req_scopes": 0,
        "actor": "attacker",
        "should_allow": 0,
    },
    {
        "label": "REVOKED-TOKEN",
        "kind": K_NORMAL,
        "claimed": "auditor",
        "token": "tok-audi-5d6e1b",
        "action": ACT_READ_AUDIT,
        "deputy": None,
        "req_scopes": 0,
        "actor": "attacker",
        "should_allow": 0,
    },
    {
        "label": "EXPIRED-TOKEN",
        "kind": K_NORMAL,
        "claimed": "deployer",
        "token": "tok-depl-old-33c7",
        "action": ACT_DEPLOY,
        "deputy": None,
        "req_scopes": 0,
        "actor": "attacker",
        "should_allow": 0,
    },
    {
        "label": "CONFUSED-DEPUTY",
        "kind": K_ON_BEHALF,
        "claimed": "summarizer",
        "token": "tok-summ-4b2d8f",
        "action": ACT_DEPLOY,
        "deputy": "deployer",
        "req_scopes": 0,
        "actor": "attacker",
        "should_allow": 0,
    },
    {
        "label": "ESCALATION",
        "kind": K_DELEGATE,
        "claimed": "summarizer",
        "token": "tok-summ-4b2d8f",
        "action": ACT_READ_CONFIG,
        "deputy": None,
        "req_scopes": SC_READ | SC_WRITE | SC_ADMIN,
        "actor": "attacker",
        "should_allow": 1,
    },
    {
        "label": "ESCALATION-USE",
        "kind": K_NORMAL,
        "claimed": "sub-agent",
        "token": "tok-deleg-0001",
        "action": ACT_WRITE_CONFIG,
        "deputy": None,
        "req_scopes": 0,
        "actor": "attacker",
        "should_allow": 0,
    },
    {
        "label": "BACKDOOR-USE",
        "kind": K_NORMAL,
        "claimed": "svc-backdoor",
        "token": "tok-backdoor-0001",
        "action": ACT_DEPLOY,
        "deputy": None,
        "req_scopes": 0,
        "actor": "attacker",
        "should_allow": 0,
    },
    {
        "label": "control",
        "kind": K_NORMAL,
        "claimed": "deployer",
        "token": "tok-depl-91e0aa",
        "action": ACT_DEPLOY,
        "deputy": None,
        "req_scopes": 0,
        "actor": "deployer",
        "should_allow": 1,
    },
    {
        "label": "control",
        "kind": K_NORMAL,
        "claimed": "orchestrator",
        "token": "tok-orch-7a1c9e",
        "action": ACT_WRITE_CONFIG,
        "deputy": None,
        "req_scopes": 0,
        "actor": "orchestrator",
        "should_allow": 1,
    },
]


def usage(program):
    print(
        f"usage: {program} [--verify] [--plant-hallucinated-api]",
        file=sys.stderr,
    )


def main():
    verify = False
    plant_hallucinated_api = False

    for argument in sys.argv[1:]:
        if argument == "--verify":
            verify = True
        elif argument == "--plant-hallucinated-api":
            plant_hallucinated_api = True
        else:
            usage(sys.argv[0])
            return 2

    # Registry
    orchestrator = add_agent("orchestrator", SC_ALL)
    summarizer = add_agent("summarizer", SC_READ)
    deployer = add_agent("deployer", SC_READ | SC_DEPLOY)
    auditor = add_agent("auditor", SC_READ)

    add_token("tok-orch-7a1c9e", orchestrator, SC_ALL, 9999, 0, -1)
    add_token("tok-summ-4b2d8f", summarizer, SC_READ, 9999, 0, -1)
    add_token(
        "tok-depl-91e0aa",
        deployer,
        SC_READ | SC_DEPLOY,
        9999,
        0,
        -1,
    )
    add_token(
        "tok-depl-old-33c7",
        deployer,
        SC_READ | SC_DEPLOY,
        100,
        0,
        -1,
    )
    add_token("tok-audi-5d6e1b", auditor, SC_READ, 9999, 1, -1)

    print("=== Identity compromise simulation ===")
    print(
        "mode: "
        + (
            "VERIFY (token binding, expiry, revocation, attenuation)"
            if verify
            else "UNMITIGATED"
        )
        + "\n"
    )

    executed = 0
    unauthorized = 0
    wrongly_denied = 0
    misattributed = 0
    escalated = 0

    for index, step in enumerate(STEPS, start=1):
        decision = decide(
            step,
            verify,
            plant_hallucinated_api=plant_hallucinated_api,
        )

        action_name = (
            "delegate"
            if step["kind"] == K_DELEGATE
            else ACT_NAME[step["action"]]
        )

        print(
            f"  [s{index:02d}] {step['label']:<16} "
            f"claimed={step['claimed']:<12} "
            f"token={step['token']:<18} "
            f"action={action_name:<12} -> ",
            end="",
        )

        if decision["allowed"]:
            executed += 1
            note = apply_effects(step, verify)

            marker = "" if step["should_allow"] else "  <-- UNAUTHORIZED"
            via = f" via {decision['via']}" if decision["via"] else ""
            print(f"ALLOWED  log={decision['logname']}{via}{marker}")

            if not step["should_allow"]:
                unauthorized += 1

            if decision["logname"] != step["actor"]:
                misattributed += 1
        else:
            marker = "  <-- WRONGLY DENIED" if step["should_allow"] else ""
            print(f"DENIED   {decision['why']}{marker}")

            if step["should_allow"]:
                wrongly_denied += 1
            note = ""

        if decision["allowed"] and note:
            print(f"         {note}")

    for token in tokens:
        if token["parent"] >= 0:
            parent_scopes = tokens[token["parent"]]["scopes"]
            if token["scopes"] & ~parent_scopes:
                escalated += 1

    print("\n=== Summary ===")
    print(f"requests                      : {len(STEPS)}")
    print(f"executed                      : {executed}")
    print(f"unauthorized executions       : {unauthorized}")
    print(f"legitimate requests denied    : {wrongly_denied}")
    print(f"escalated tokens minted       : {escalated}")
    print(
        "persistent backdoor identity  : "
        + ("yes" if find_agent("svc-backdoor") >= 0 else "no")
    )
    print(f"audit entries, wrong identity : {misattributed}")
    print(
        "result                        : "
        + (
            "IDENTITY COMPROMISE SUCCEEDED (attack succeeded)"
            if unauthorized
            else "compromise contained"
        )
    )

    return 1 if unauthorized else 0


if __name__ == "__main__":
    raise SystemExit(main())
