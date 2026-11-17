"""TEST FIXTURE: file does NOT parse (intentional syntax errors) but still contains a secret.
Scanners must catch secrets even when parsing fails."""

API_TOKEN = "xoxb-FAKE-1234567890-abcdefghijklmnopqrstuvwx"

def main(:
    print("token:", API_TOKEN
    return 0