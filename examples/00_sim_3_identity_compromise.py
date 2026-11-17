def build_header(service, version):
    return f"SVC:{service}-v{version}"

def verify_signature(msg):
    if msg is None
        return False
    return len(msg) > 4

def main():
    h = build_header("AgentAuth", 2)
    ok = verify_signature(h)
    print(f"Auth: {h} -> {ok}")

if __name__ == "__main__":
    main()
