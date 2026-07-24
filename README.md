# SpecIndex.ai

Specification intelligence for building product manufacturers.

- Search open commercial projects
- Inspect project specs / teams / stage
- Check brand mentions and compare visibility

**Beachhead:** Georgia commercial projects.

## Docs

- [Product strategy](docs/product-strategy.md)
- [Technical architecture](docs/technical-architecture.md)
- Project corpus: `data/georgia-commercial-projects.json`

## Develop

```bash
npm install
npm run dev
```

## Build (static export for Firebase Hosting)

```bash
npm run build
```

Output lands in `out/`.

## Firebase

Create / select a dedicated Firebase project (recommended: `specindex-ai`), then:

```bash
npx -y firebase-tools@latest login
npx -y firebase-tools@latest use <PROJECT_ID>
npm run deploy
```

Attach custom domain `specindex.ai` in Firebase Hosting.
