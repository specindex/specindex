import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
  // Default is 60s, bumped to 180s in 2026-07-26 (GitHub Actions runners
  // are slower/more contended than local hardware). Bumped again 2026-07-29:
  // /reporting still legitimately fetches the full corpus (~175K+ rows,
  // ~1,750 sequential paginated requests -- see docs/ROADMAP.md item 44's
  // follow-up for why every OTHER page stopped doing this), and that many
  // round trips plus lib/projects.ts's fetch-failure retries can land close
  // to 180s even without anything actually being wrong.
  staticPageGenerationTimeout: 300,
  // Next spawns one static-generation worker process per CPU core by
  // default (10 locally) -- each gets its own copy of lib/projects.ts's
  // in-process request queue, so the real global concurrency against the
  // API is (this number x MAX_CONCURRENT_REQUESTS there), not just the
  // latter alone. Capping worker processes directly makes that ceiling
  // predictable instead of an estimate. Added 2026-07-29 alongside that
  // queue, after per-page pacing alone still weren't enough to stop
  // parallel pages from starving each other's requests.
  experimental: { cpus: 2 },
};

export default nextConfig;
