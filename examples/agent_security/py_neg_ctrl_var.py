"""NEGATIVE CONTROL: suspicious-looking names, but NO secrets. Should NOT be flagged."""
import os

api_key = os.environ.get("API_KEY")            # read from environment
password = os.environ["DB_PASSWORD"]           # read from environment
token = None                                   # unset
private_key_path = "/etc/app/keys/id_rsa"      # path only, not key material

def main():
    if not api_key:
        raise SystemExit("missing configuration")
    print("key path:", private_key_path, "token set:", token is not None)

if __name__ == "__main__":
    main()