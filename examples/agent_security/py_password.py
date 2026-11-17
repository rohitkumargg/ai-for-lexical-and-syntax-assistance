"""TEST FIXTURE: hardcoded password (fake value)"""

ADMIN_PASSWORD = "admin123!"

def check_login(user: str, password: str) -> bool:
    return user == "admin" and password == ADMIN_PASSWORD

if __name__ == "__main__":
    print("login ok:", check_login("admin", "guess"))