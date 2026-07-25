import json
import urllib.parse
import urllib.request

headers = {"User-Agent": "SpecIndex/1.0"}
params = urllib.parse.urlencode({
    "$limit": 10,
    "$where": "issuance_date >= '2026-05-01T00:00:00.000' AND (job_type = 'NB' OR job_type = 'A1')",
    "$order": "issuance_date DESC",
})
url = f"https://data.cityofnewyork.us/resource/ipu4-2q9a.json?{params}"

try:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        d = json.loads(resp.read())
        print("NYC DOB Permits count:", len(d))
        for p in d:
            print(p.get("job__"), p.get("issuance_date")[:10], p.get("job_type"), p.get("house__"), p.get("street_name"), p.get("owner_s_first_name"), p.get("owner_s_last_name"), p.get("proposed_occupancy"))
except Exception as e:
    print("NYC error:", e)
