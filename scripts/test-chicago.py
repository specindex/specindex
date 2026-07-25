import json
import urllib.parse
import urllib.request

headers = {"User-Agent": "SpecIndex/1.0"}
params = urllib.parse.urlencode({
    "$limit": 10,
    "$where": "reported_cost > 1000000 AND issue_date >= '2026-01-01T00:00:00.000'",
    "$order": "issue_date DESC",
})
url = f"https://data.cityofchicago.org/resource/ydr8-5enu.json?{params}"

req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req, timeout=10) as resp:
    d = json.loads(resp.read())
    print("Chicago $1M+ permits count:", len(d))
    for p in d:
        print(f"Permit #{p.get('permit_')}: {p.get('issue_date')[:10]} | ${float(p.get('reported_cost',0)):,.0f} | {p.get('street_number','')} {p.get('street_name','')} | {p.get('work_description','')[:80]}")
