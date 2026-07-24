# Connect specindex.ai → Firebase Hosting

**Live now:** https://specindex-ai.web.app  
**Project:** `specindex-ai`  
**Console:** https://console.firebase.google.com/project/specindex-ai/hosting

Custom domains are configured in the Firebase Console (CLI cannot finish DNS verification for you).

## Steps

1. Open [Hosting for specindex-ai](https://console.firebase.google.com/project/specindex-ai/hosting).
2. Click **Add custom domain**.
3. Enter `specindex.ai` (optionally also add `www.specindex.ai` and redirect www → apex, or the reverse).
4. Firebase will show DNS records. At your registrar (Namecheap, Cloudflare, Google Domains, Squarespace, etc.), add them.

### Typical records (confirm exact values in the console)

| Type | Host | Value |
|---|---|---|
| TXT | `@` or `specindex.ai` | Verification string from Firebase (keep permanently) |
| A | `@` or `specindex.ai` | IP(s) shown in Firebase (often includes `199.36.158.100`) |
| A / CNAME | `www` | As shown in Firebase (A to same IP, or CNAME to `specindex-ai.web.app`) |

Host field tips:

- Namecheap / Squarespace: use `@` for apex, `www` for subdomain
- Cloudflare / Google Cloud DNS: often use `specindex.ai` or leave blank for apex

5. Click **Verify** in Firebase after TXT propagates (minutes to a few hours; up to 24h).
6. Wait for status **Connected** and SSL provisioning (usually a few hours, up to 24h).

## After DNS is connected

- Visit https://specindex.ai and https://www.specindex.ai
- Confirm SSL padlock
- Redeploy anytime with: `npm run deploy` from this repo

## Troubleshooting

- **Needs setup:** A/AAAA not pointed yet or not propagated
- **Pending / Minting certificate:** ownership OK; wait for SSL
- **CAA errors:** allow `letsencrypt.org` and `pki.goog` in CAA records
