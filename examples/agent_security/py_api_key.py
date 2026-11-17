"""TEST FIXTURE: hardcoded API key (fake values)"""
import requests

API_KEY = "sk_live_FAKE0123456789abcdefghijklmnop"
AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

def call_api():
    return requests.get("https://api.example.com/v1/data",
                        headers={"Authorization": f"Bearer {API_KEY}"})

if __name__ == "__main__":
    call_api()