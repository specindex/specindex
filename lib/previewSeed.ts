/**
 * Illustrative data for the logged-in workspace preview.
 *
 * WHY THIS FILE EXISTS, AND WHY IT IS QUARANTINED HERE.
 *
 * Maine really holds 138 projects, of which 3 have any document and most have
 * no value, no owner and sometimes no name (11 of the first 100 are titled
 * only a BGS number). Rendering the workspace against that shows the product
 * honestly but makes it impossible to judge the DESIGN: every row looks the
 * same, so you cannot tell whether the layout works when a row has something
 * to say.
 *
 * These records are the handoff mock's own illustrative projects. They are
 * what the corpus looks like at the coverage we are building toward, not what
 * it looks like today.
 *
 * RULES, because seeded demo data has a way of escaping:
 *   - Only /preview/* imports this. Nothing in app/project, app/projects or
 *     lib/projects.ts may.
 *   - Every record carries `isSeed: true` and the UI labels the screen as
 *     sample data. A demo that cannot be told apart from production is how a
 *     number nobody verified ends up in a board deck.
 *   - Never written to Postgres, never merged into a corpus count.
 *
 * The one real record (Maine State Prison, SPX-6700284) is kept alongside them
 * deliberately, so the contrast between a genuinely sparse record and a rich
 * one stays visible in the same list.
 */

export type SeedProject = {
  id: string;
  isSeed: true;
  name: string;
  city: string;
  state: string;
  owner: string;
  score: number | null;
  value: string;
  status: string;
  docCount: number;
  divisions: { code: string; label: string }[];
  urgency: string | null;
  urgent: boolean;
  source: string;
  tracked: boolean;
};

export const SEED_PROJECTS: SeedProject[] = [
  {
    id: "seed-portland-jetport",
    isSeed: true,
    name: "Portland Jetport concourse improvements",
    city: "Portland", state: "ME", owner: "City of Portland",
    score: 71, value: "$18.4M", status: "design",
    docCount: 41,
    divisions: [{ code: "26 50 00", label: "Lighting" }, { code: "23 00 00", label: "HVAC" }],
    urgency: "Design phase", urgent: false,
    source: "City capital plan, Jul 2026",
    tracked: true,
  },
  {
    id: "seed-northern-light",
    isSeed: true,
    name: "Northern Light Health ambulatory expansion",
    city: "Bangor", state: "ME", owner: "Northern Light Health",
    score: 68, value: "$54M", status: "bidding",
    docCount: 63,
    divisions: [
      { code: "26 50 00", label: "Lighting" },
      { code: "22 00 00", label: "Plumbing" },
      { code: "23 00 00", label: "HVAC" },
    ],
    urgency: "Basis of design open", urgent: true,
    source: "Permit filing, City of Bangor",
    tracked: true,
  },
  {
    id: "seed-auburn-cold-storage",
    isSeed: true,
    name: "Auburn cold-storage distribution center, phase 2",
    city: "Auburn", state: "ME", owner: "Androscoggin Logistics",
    score: 62, value: "$31M", status: "permitting",
    docCount: 22,
    divisions: [
      { code: "26 50 00", label: "Lighting" },
      { code: "13 00 00", label: "Special construction" },
    ],
    urgency: "Permitting", urgent: false,
    source: "Androscoggin County permit record",
    tracked: true,
  },
];

export type SeedNote = { id: string; kind: string; when: string; text: string; project: string };

export const SEED_NOTES: SeedNote[] = [
  {
    id: "sn1", kind: "NOTE", when: "Aug 7",
    text: "Discovery record, no spec yet. This is the whole point of tracking early: when the project manual publishes, we are the first call the specifier gets, not the last.",
    project: "Maine State Prison Gatehouse Improvement Project",
  },
  {
    id: "sn2", kind: "CALL", when: "Aug 6",
    text: "Talked to the city project manager. Acuity got in through the on-call architect's standard template, not a preference. He is open to an or-equal at 90% CD.",
    project: "Portland Jetport concourse improvements",
  },
  {
    id: "sn3", kind: "EMAIL", when: "Aug 7",
    text: "Sent the lighting cut sheets to the Emory facilities lead. She asked for a mockup in the third-floor corridor.",
    project: "Northern Light Health ambulatory expansion",
  },
];

export const SEED_CHANGES = [
  { tag: "New", tone: "amber", headline: "Discovered before any bid portal listed it, no spec published yet",
    project: "Maine State Prison Gatehouse Improvement Project", when: "2 days ago" },
  { tag: "Doc", tone: "green", headline: "Amendment 0004 posted, response deadline moved to May 22",
    project: "Northern Light Health ambulatory expansion", when: "Yesterday" },
  { tag: "Team", tone: "grey", headline: "General contractor awarded, Consigli Construction",
    project: "Auburn cold-storage distribution center", when: "2 days ago" },
];

export const SEED_STAGES = [
  { key: "watching", label: "Watching", dot: "#8A938C", count: 2 },
  { key: "engaged", label: "Specifier engaged", dot: "#C0631A", count: 1 },
  { key: "specified", label: "Spec named", dot: "#16643A", count: 1 },
  { key: "closed", label: "Closed out", dot: "#5B655E", count: 0 },
];

export const SEED_MENTIONS = [
  { brand: "Acuity Brands", rival: true, when: "2h",
    text: "Named basis of design, Portland Jetport concourse, division 26 50 00." },
  { brand: "Your brand", rival: false, when: "1d",
    text: "Listed as an approved equal on the Northern Light package." },
  { brand: "Your brand", rival: false, when: "3d",
    text: "Basis of design held through phase 2 at Auburn cold storage." },
];

// A stale bar is shown on purpose. The handoff is explicit that freshness must
// be able to look bad, or it is decoration rather than a signal.
export const SEED_FRESHNESS = [
  { label: "Maine permits and portals", when: "6h ago", pct: 92, stale: false },
  { label: "SAM.gov solicitations", when: "12h ago", pct: 78, stale: false },
  { label: "Spec document parsing", when: "2d ago", pct: 34, stale: true },
];
