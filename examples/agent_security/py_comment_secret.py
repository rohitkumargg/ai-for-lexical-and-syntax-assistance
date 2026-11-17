"""TEST FIXTURE: secret leaked inside a comment (fake values)"""

# TODO: remove before commit -- prod DB password is "Pr0d!Passw0rd#2024"
# github token for CI: ghp_FAKE1234567890abcdefghijklmnopqrstuv

def main():
    print("nothing suspicious in the code itself")

if __name__ == "__main__":
    main()