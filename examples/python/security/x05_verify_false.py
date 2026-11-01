import requests
r = requests.get("https://example.com", verify=False)
print(r.status_code)
