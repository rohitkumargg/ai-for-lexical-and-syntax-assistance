import requests
r = requests.get("https://example.com", verify=True)
print(r.status_code)
