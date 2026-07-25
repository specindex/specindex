import json
import urllib.parse
import urllib.request

headers = {"User-Agent": "SpecIndex/1.0"}
params = urllib.parse.urlencode({
    "$limit": 10,
    "$where": "issue_date >= '2026-05-01T00:00:00.000'",
    "$order": "issue_date DESC",
})
url = f"https://data.cityofnewyork.us/resource/3h2n-5cm9.json?{params}"

try:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        d = json.loads(resp.read())
        print("NYC permits count:", len(d))
        for p in d:
            print(p)
except Exception as e:
    print("NYC error:", e)
