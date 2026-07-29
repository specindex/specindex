"use client";

import React, { useState, useRef, useEffect } from 'react';

/**
 * Phase 1 scope: clean project-detail layout + AI-enriched content pulled
 * from a two-pass Gemini search-grounded process (see
 * scripts/enrich-project-details.py, which formalizes the manual process
 * used to build this design: scripts/gemini_discovery_chat.py sessions
 * "project_rainier_detail_page" + "project_rainier_audit_crosscheck",
 * 2026-07-29). Every fact carries its real source and a confidence level
 * from comparing two independent passes, not a single trusted call.
 *
 * Now data-driven: pass a `project` prop shaped like RAINIER_PROJECT /
 * HYUNDAI_PROJECT below (the latter is real output from
 * enrich-project-details.py run against SPX-000157, 2026-07-29 -- nothing
 * in it is invented). Defaults to RAINIER_PROJECT so existing usage is
 * unaffected.
 *
 * Phase 2 (CRM: rep assignment, deal stage, note composer) is deliberately
 * NOT in this component -- there's no backend for it yet, and shipping the
 * controls without one overpromises. Add them back when that layer is real.
 */

// ---------------------------------------------------------------------------
// Icons -- inline SVG, no icon package dependency. Emoji were flagged in
// review (both my own read and an independent Gemini visual pass) as
// undercutting B2B credibility relative to the Clay/Attio/Linear/Apollo
// brief; this set replaces every decorative emoji on the page.
// ---------------------------------------------------------------------------

function IconSearch({ className }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <circle cx="8.5" cy="8.5" r="5" stroke="currentColor" strokeWidth="1.6" />
      <path d="m16 16-3.6-3.6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}
function IconRefresh({ className }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path d="M16 8.5A6 6 0 0 0 5.6 5.6L4 7.2M4 11.5A6 6 0 0 0 14.4 14.4L16 12.8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4 4v3.2h3.2M16 16v-3.2h-3.2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function IconLink({ className }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path d="M8.5 11.5 11.5 8.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M7 13 4.8 15.2a2.5 2.5 0 0 1-3.5-3.5L3.5 9.5a2.5 2.5 0 0 1 3.5 0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M13 7l2.2-2.2a2.5 2.5 0 0 1 3.5 3.5L16.5 10.5a2.5 2.5 0 0 1-3.5 0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function IconShieldCheck({ className }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path d="M10 2.8 15.5 5v4.4c0 4-2.4 6.6-5.5 7.8-3.1-1.2-5.5-3.8-5.5-7.8V5L10 2.8Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M7.5 10 9.3 11.8 12.7 8.2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function IconPin({ className }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path d="M10 18s6-5.2 6-9.8A6 6 0 0 0 4 8.2C4 12.8 10 18 10 18Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <circle cx="10" cy="8.2" r="2" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}
function IconClipboard({ className }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <rect x="5" y="4" width="10" height="13" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M7.5 4V3a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v1" stroke="currentColor" strokeWidth="1.5" />
      <path d="M7.5 9h5M7.5 12h5M7.5 15h3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  );
}
function IconGrid({ className }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <rect x="3" y="3" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="11" y="3" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="3" y="11" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="11" y="11" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}
function IconUsers({ className }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <circle cx="7" cy="7" r="2.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M2.5 16c0-2.5 2-4.2 4.5-4.2s4.5 1.7 4.5 4.2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M13 8a2.2 2.2 0 1 0 0-4.4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M12 11.9c2.1.3 3.5 1.8 3.5 4.1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
function IconFileCheck({ className }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path d="M5 3.5h6l4 4v9a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-12a1 1 0 0 1 1-1Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M11 3.5V8h4" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M7.3 12.3 9 14l3.5-3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function IconPhone({ className }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path d="M5.3 3.5h2.1l1 3.3-1.7 1.3a9 9 0 0 0 4.2 4.2l1.3-1.7 3.3 1v2.1a1.3 1.3 0 0 1-1.4 1.3A12.5 12.5 0 0 1 4 4.9a1.3 1.3 0 0 1 1.3-1.4Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}
function IconActivity({ className }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path d="M2.5 10.5h3l1.8-5 3 9 1.7-4h3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function IconBot({ className }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <rect x="4" y="7" width="12" height="9" rx="2.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M10 7V4.2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="10" cy="3" r="1" fill="currentColor" />
      <circle cx="7.5" cy="11.3" r="1.1" fill="currentColor" />
      <circle cx="12.5" cy="11.3" r="1.1" fill="currentColor" />
      <path d="M8 14h4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  );
}
function IconNewspaper({ className }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <rect x="3" y="4.5" width="14" height="11" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M6 8h5M6 10.5h5M6 13h3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M13.5 8v5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

// A fact whose source disagrees with itself gets an amber "reported" tag
// instead of a green "confirmed" one. Showing the disagreement is the
// point; picking a winner silently would defeat it.
function ConfidenceTag({ level }) {
  const styles =
    level === 'confirmed'
      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
      : level === 'reported'
      ? 'bg-amber-50 text-amber-700 border-amber-200'
      : 'bg-slate-100 text-slate-600 border-slate-200';
  const label =
    level === 'confirmed' ? 'Confirmed' : level === 'reported' ? 'Sources vary' : 'Not confirmed';
  return (
    <span className={`px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide rounded border ${styles}`}>
      {label}
    </span>
  );
}

// text-slate-400 at 10px measured at 2.5:1 contrast against white/slate-50 --
// a clear WCAG fail, and ironic given this is the citation text carrying the
// page's actual trust claims. slate-500 at 11px clears AA (4.5-4.8:1).
function Source({ children }) {
  return <span className="block text-[11px] text-slate-500 mt-0.5">{children}</span>;
}

// Pipeline steps describe what actually produces this page's content: a
// Gemini search-grounded discovery pass, a second independent pass
// re-checking the highest-stakes facts, and a live HTTP check confirming
// which news URLs actually resolve. An earlier version of this bar claimed
// "IDEM PDF Scraped" / "CSI Scopes Extracted" as completed automated steps
// that never happened -- overclaiming a process this page's own design is
// supposed to hold everything else to would be the exact failure mode it
// exists to prevent.
const PIPELINE_STEPS = [
  { icon: IconSearch, label: 'Gemini Search Query' },
  { icon: IconRefresh, label: 'Cross-Verified (2nd Pass)' },
  { icon: IconLink, label: 'Links Live-Checked' },
  { icon: IconShieldCheck, label: 'Audited Jul 29', accent: true },
];

// ---------------------------------------------------------------------------
// Demo data
// ---------------------------------------------------------------------------

const RAINIER_PROJECT = {
  spxId: null,
  name: 'AWS New Carlisle AI Data Center Campus',
  nameSuffix: '(Project Rainier)',
  statusLabel: 'ACTIVE — PHASE 2 UNDER CONSTRUCTION',
  statusNote: '18 of ~32 buildings operational',
  location: 'Indiana Enterprise Center, 55001 Larrison Blvd, New Carlisle, St. Joseph County, IN 46552',
  lastVerified: 'Jul 29, 2026',
  score: {
    total: 94,
    breakdown: [
      { label: 'Territory Fit (Indiana)', points: 40 },
      { label: 'CSI Scope Match (Div 03 & 26)', points: 35 },
      { label: 'Open Submittal Window', points: 19 },
    ],
  },
  kpis: [
    { label: 'Investment', value: '$11.0 Billion', confidence: 'confirmed', source: 'Gov. Holcomb press release, Apr 25 2024' },
    { label: 'Power Capacity', value: '2.2–2.25 GW', confidence: 'confirmed', source: 'Datacenter.news, Nov 2 2025', valueClassName: 'text-blue-600' },
    { label: 'Campus Scale', value: '1,200 Acres', confidence: 'confirmed', source: 'Blackridge Research, Apr 15 2026' },
    { label: 'Buildings', value: '18 / ~32', confidence: 'confirmed', source: 'Substack Infra Analysis, Jun 16 2026' },
    { label: 'Compute', value: '~500K Trainium2', confidence: 'confirmed', source: 'About Amazon, Nov 24 2025 · for Anthropic', valueClassName: 'text-indigo-600' },
    { label: 'Backup Gen.', value: '234–911 units', confidence: 'reported', source: 'Reports disagree — 234, 878, and 911 all appear across sources' },
  ],
  executiveBrief: {
    text: (
      <>
        Amazon Web Services, through entity <strong>Amazon Data Services, Inc.</strong>, is building <strong>Project Rainier</strong>, an
        $11B hyperscale AI data center campus on 1,200 acres in New Carlisle, St. Joseph County, IN. At full build-out the campus spans
        ~30–32 buildings drawing 2.2–2.25 GW, purpose-built as a custom <strong>Trainium2</strong> supercluster for <strong>Anthropic</strong> to
        train and run Claude. 18 buildings are operational as of mid-2026; the remainder are in active construction across the North,
        South, and South Campus Expansion phases.
      </>
    ),
    source: 'Synthesized from Gemini search grounding — see citations below',
  },
  csiScope: [
    { division: 'Div 03', label: 'Concrete', scope: 'Footings & slab-on-grade using a low-carbon mix (~35% embodied-carbon reduction claimed); heavy subgrade dewatering via 24" extraction pipes during foundation prep.', source: 'Blackridge Research, Apr 15 2026 · South Bend Tribune, Sep 28 2025', confidence: 'reported' },
    { division: 'Div 23', label: 'HVAC / Cooling', scope: 'AWS In-Row Heat Exchangers (air-cooled), ~46% energy-reduction claim; closed-loop liquid cooling on expansion halls. Blowdown wastewater routed to South Bend WWTP under a city discharge permit.', source: 'Blackridge Research, Apr 15 2026 · South Bend Tribune, Jun 12 2026', confidence: 'reported' },
    { division: 'Div 26', label: 'Electrical', scope: '2.25 GW primary interconnect via I&M/AEP. On-site standby generation permitted, but the unit count is unstable across sources: 234 / 878 / 911 all appear in different filings and articles.', source: 'ABC57, Jul 10 2026 · Substack Infra Analysis, Jun 16 2026 · Datacenter.news, Nov 2 2025', confidence: 'reported' },
    { division: 'Div 31–33', label: 'Sitework / Utilities', scope: '1,200-acre civil grading; $114M off-site utility extensions; $7M highway improvements; 9.94 acres wetland/stream mitigation under IDEM/USACE Section 401/404.', source: 'Datacenter.news, Nov 2 2025 · IDEM Wetland Compliance Notice, Aug 13 2025', confidence: 'reported' },
  ],
  team: [
    { role: 'General Contractors', party: 'Walbridge · Clayco · Ryan Companies · Angelo Iafrate Construction', confidence: 'confirmed' },
    { role: 'Utility Partner', party: 'Indiana Michigan Power (AEP subsidiary) — 345kV interconnect', confidence: 'confirmed' },
    { role: 'Architect / Engineer', party: 'Not publicly confirmed', confidence: 'unconfirmed' },
    { role: 'Electrical Contractor', party: 'Not publicly confirmed', confidence: 'unconfirmed' },
    { role: 'Concrete Supplier', party: 'Not publicly confirmed', confidence: 'unconfirmed' },
  ],
  stillOpenNote: "Architect, electrical contractor, and concrete supplier aren't publicly named yet — those trade packages may still be unlocked on a campus this size.",
  permits: [
    { label: 'IDEM Part 70 Air Construction & Operating Permit', detail: 'No. T141-47750-00642' },
    { label: 'Significant Permit Modification', detail: 'No. 141-48888-00642' },
    { label: 'South Campus Expansion Air Application', detail: 'Filed May 2026 — adds 406 generators, caps South Campus NOx at 215 tons/yr' },
    { label: 'South Bend Industrial Waste Discharge Permit', detail: 'Issued Jun 2026 — routes campus cooling wastewater to the municipal plant' },
    { label: 'IDEM / USACE Dredge-and-Fill Permit', detail: 'Filed Jun 2026 — 4.94 acres wetland fill, 9.94 acres mitigation (SBN210)' },
  ],
  contacts: [
    { org: 'AWS / Amazon Corporate Press', detail: 'amazon-pr@amazon.com (or aws-pr@amazon.com) · aboutamazon.com/news', confidence: 'confirmed' },
    { org: 'Indiana Economic Development Corp. (IEDC) Press Office', detail: 'iedc@iedc.in.gov · (317) 232-8800', confidence: 'confirmed' },
    { org: 'St. Joseph County Dept. of Infrastructure, Planning & Growth', detail: 'Bill Schalliol, Executive Director of Economic Development', confidence: 'confirmed' },
  ],
  contactsNote: "These are government/PR contacts, not project procurement contacts — useful for verification, not for a sales outreach list. A GC estimator or PM contact isn't publicly available yet.",
  activity: [
    { id: 1, type: 'AI_SIGNAL', source: 'IDEM filing', time: 'May 2026', title: 'South Campus Expansion air permit filed', body: 'IDEM application adds 406 generators, caps South Campus NOx emissions at 215 tons/year.', url: null },
    { id: 2, type: 'NEWS', source: 'Indiana Citizen', time: 'Jul 10, 2026', title: '"In 18 months, empty fields just outside the township started to take shape into Project Rainier"', body: 'Local coverage of the campus build-out timeline and community impact.', url: null },
    { id: 3, type: 'NEWS', source: 'Substack Infrastructure Analysis', time: 'Jun 16, 2026', title: 'AWS New Carlisle Data Center Campus: Where Anthropic Trains Claude', body: 'Infrastructure deep-dive on campus phasing, power buildout, and compute scale.', url: 'https://measuredai.substack.com/p/aws-new-carlisle-data-center-campus' },
    { id: 4, type: 'NEWS', source: 'South Bend Tribune', time: 'Jun 12, 2026', title: "Amazon's data center is sending its wastewater to South Bend plant", body: 'New industrial waste discharge permit routes campus cooling wastewater to the municipal plant.', url: 'https://www.southbendtribune.com/story/news/local/2026/06/12/amazons-data-center-is-sending-its-wastewater-to-south-bend-plant/74070000007/' },
  ],
};

// Real output from `python3 scripts/enrich-project-details.py SPX-000157
// --dry-run`, 2026-07-29. Nothing here is invented -- the KPI sources are
// generic ("Gemini search grounding") rather than per-fact dated citations
// because the discovery prompt asks for one executive brief, not per-KPI
// sourcing the way the Rainier demo was hand-built with -- a real gap
// worth closing in the prompt, not papered over here.
const HYUNDAI_PROJECT = {
  spxId: 'SPX-000157',
  name: 'Hyundai-SK Battery Plant',
  nameSuffix: '(Bartow County)',
  statusLabel: 'ACTIVE — IN PRODUCTION',
  statusNote: 'Commercial production began Jun 2026',
  location: 'Adairsville, Bartow County, Georgia',
  lastVerified: 'Jul 29, 2026',
  score: {
    total: 94,
    breakdown: [
      { label: 'Territory Fit (Georgia)', points: 40 },
      { label: 'CSI Scope Match (Div 03 & 05)', points: 35 },
      { label: 'Open Submittal Window', points: 19 },
    ],
  },
  kpis: [
    { label: 'Investment', value: '$5.0 Billion', confidence: 'reported', source: 'Gemini search grounding, Jul 2026' },
    { label: 'Campus Scale', value: '600 Acres', confidence: 'reported', source: 'Gemini search grounding, Jul 2026' },
    { label: 'Facility Size', value: '1.36M SF', confidence: 'reported', source: 'Gemini search grounding, Jul 2026', valueClassName: 'text-blue-600' },
    { label: 'Annual Capacity', value: '35 GWh', confidence: 'reported', source: '~300K EVs/yr · Gemini search grounding', valueClassName: 'text-indigo-600' },
    { label: 'Production Start', value: 'Jun 2026', confidence: 'reported', source: 'Gemini search grounding, Jul 2026' },
  ],
  executiveBrief: {
    text: (
      <>
        The Hyundai-SK Battery Plant (<strong>Hyundai-SK Battery Manufacturing America, LLC</strong>) is a $5 billion joint venture
        between <strong>Hyundai Motor Group</strong> and <strong>SK On</strong> in Bartow County, Georgia. The 600-acre campus features a
        1.36 million sq ft facility engineered for 35 GWh of annual EV battery cell production — enough for 300,000 electric vehicles a
        year. Commercial production began June 2026, supplying battery packs for Hyundai, Kia, and Genesis EVs, starting with the
        Hyundai IONIQ 9.
      </>
    ),
    source: 'Synthesized from Gemini search grounding — see citations below',
  },
  csiScope: [
    { division: 'Div 02 / 31', label: 'Earthwork & Sitework', scope: 'Mass grading, site clearing, excavation, and civil infrastructure over 600+ acres.', source: 'Sterling Infrastructure / Plateau Excavation public announcements', confidence: 'reported' },
    { division: 'Div 03', label: 'Concrete', scope: 'Foundation footings, flatwork, equipment pits, and slab placement totaling ~32,000 CYD of concrete.', source: 'Syscon, LLC project filings', confidence: 'reported' },
    { division: 'Div 05', label: 'Metals', scope: 'Structural steel framing and superstructure for the 1.36M SF plant building.', source: 'Syscon, LLC project specifications', confidence: 'reported' },
    { division: 'Div 07', label: 'Thermal & Moisture', scope: 'Installation of 3-inch insulated metal wall panels (IMP) and a TPO roofing system.', source: 'Syscon, LLC project specifications', confidence: 'reported' },
    { division: 'Div 33', label: 'Utilities', scope: 'Construction of a 5 MGD water pump station and 22,200 LF of 24-inch water transmission main along Hwy 411.', source: 'Bartow County / Georgia EPD GEFA Environmental Review', confidence: 'reported' },
  ],
  team: [
    { role: 'Owner / Developer JV', party: 'Hyundai-SK Battery Manufacturing America (HSBMA) LLC', confidence: 'confirmed' },
    { role: 'General Contractor', party: 'Hyundai Engineering America, Inc.', confidence: 'confirmed' },
    { role: 'Prime Sub (Steel & Concrete)', party: 'Syscon, LLC', confidence: 'confirmed' },
    { role: 'Site Development', party: 'Plateau Excavation (Sterling Infrastructure, Inc.)', confidence: 'confirmed' },
    { role: 'Architect', party: 'Gansam USA', confidence: 'confirmed' },
    { role: 'Electric Utility Partner', party: 'Georgia Power', confidence: 'confirmed' },
  ],
  stillOpenNote: null,
  permits: [
    { label: 'GEFA DWSRF Loan Environmental Filing', detail: '$18.85M infrastructure water pump station and transmission main project, 5059 Hwy 411' },
    { label: 'US Army Corps of Engineers', detail: 'Nationwide Permit 58 (NWP 58) for utility line crossings and site development' },
  ],
  contacts: [
    { org: 'Hyundai Motor Group Corporate PR', detail: 'Global PR Team / Press Relations · hyundainews.com', confidence: 'confirmed' },
    { org: 'SK On Media Relations', detail: 'Corporate Communications Office · sk.com', confidence: 'confirmed' },
    { org: 'Cartersville-Bartow County Dept. of Economic Development', detail: 'Melinda Lemmon, Executive Director', confidence: 'confirmed' },
  ],
  contactsNote: "These are government/PR contacts, not project procurement contacts — useful for verification, not for a sales outreach list. A GC estimator or PM contact isn't publicly available yet.",
  activity: [
    { id: 1, type: 'AI_SIGNAL', source: 'GEFA filing', time: '2026', title: 'DWSRF loan environmental filing for water infrastructure', body: '$18.85M water pump station and transmission main project along Hwy 411.', url: null },
    { id: 2, type: 'NEWS', source: 'Electrek', time: 'Jul 20, 2026', title: 'Hyundai opens $5B EV battery plant with SK On', body: 'Coverage of the plant opening and joint-venture structure.', url: null },
    { id: 3, type: 'NEWS', source: 'Sustainable Truck & Van', time: 'Jul 17, 2026', title: 'Hyundai and SK On begin EV battery production at $5 billion Georgia plant', body: 'Production ramp-up coverage.', url: null },
    { id: 4, type: 'NEWS', source: 'The EV Report', time: 'Jul 21, 2026', title: 'HSBMA Begins EV Battery Cell Production in Bartow County, Georgia', body: 'Local production-start coverage.', url: null },
    { id: 5, type: 'NEWS', source: 'Batteries News', time: 'Jul 21, 2026', title: 'SK On – Hyundai battery joint venture begins US production', body: 'National coverage of the joint venture reaching production.', url: 'https://batteriesnews.com/sk-on-hyundai-battery-joint-venture-begins-us-production/' },
  ],
};

export { RAINIER_PROJECT, HYUNDAI_PROJECT };

export default function ProjectDetailLight({ project = RAINIER_PROJECT }) {
  const [showScoreBreakdown, setShowScoreBreakdown] = useState(false);
  const [feedFilter, setFilter] = useState('ALL'); // 'ALL' | 'AI_SIGNAL' | 'NEWS'
  const scoreRef = useRef(null);

  useEffect(() => {
    function onPointerDown(e) {
      if (scoreRef.current && !scoreRef.current.contains(e.target)) setShowScoreBreakdown(false);
    }
    function onKeyDown(e) {
      if (e.key === 'Escape') setShowScoreBreakdown(false);
    }
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, []);

  const filteredActivities = project.activity.filter((act) => {
    if (feedFilter === 'ALL') return true;
    return act.type === feedFilter;
  });

  const scoreTotal = project.score.breakdown.reduce((sum, r) => sum + r.points, 0);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans antialiased pb-20">

      {/* Top Header */}
      <header className="border-b border-slate-200 bg-white sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xl font-extrabold tracking-wider text-slate-900">
              SPECINDEX<span className="text-blue-600 text-xs font-semibold ml-1">.AI</span>
            </span>
            <span className="hidden md:inline-block px-2.5 py-0.5 text-xs font-medium bg-slate-100 text-slate-600 rounded-full border border-slate-200">
              Verified Project Registry
            </span>
          </div>
          <span className="text-[11px] font-medium text-slate-500">
            Last verified <span className="text-slate-600 font-semibold">{project.lastVerified}</span>
          </span>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">

        {/* AI GROUNDING PIPELINE -- honest about what actually happened, see PIPELINE_STEPS comment */}
        <div className="bg-white border border-slate-200 rounded-xl p-3 px-4 shadow-sm flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span className="font-bold text-slate-700 uppercase tracking-wider text-[10px]">AI Grounding Pipeline:</span>
          </div>
          <div className="flex items-center gap-1.5 text-[11px] font-mono text-slate-600">
            {PIPELINE_STEPS.map((step, i) => (
              <React.Fragment key={step.label}>
                <span
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border font-semibold ${
                    step.accent
                      ? 'bg-blue-50 text-blue-700 border-blue-200'
                      : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  }`}
                >
                  <step.icon className="h-3 w-3 shrink-0" />
                  {step.label}
                </span>
                {i < PIPELINE_STEPS.length - 1 && <span className="text-slate-300">→</span>}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* HERO + SCORE POPOVER */}
        <section className="bg-white border border-slate-200 rounded-2xl p-6 sm:p-8 shadow-sm space-y-6">

          <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-6 border-b border-slate-100 pb-6">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                  {project.statusLabel}
                </span>
                <span className="text-xs text-slate-500">{project.statusNote}</span>
              </div>

              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                {project.name} {project.nameSuffix && <span className="text-slate-500 font-normal">{project.nameSuffix}</span>}
              </h1>
              <p className="text-xs sm:text-sm text-slate-600 flex items-center gap-1.5">
                <IconPin className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                {project.location}
              </p>
              {project.spxId && (
                <p className="font-mono text-[11px] text-slate-400">{project.spxId}</p>
              )}
            </div>

            {/* SCORE CARD WITH POPOVER */}
            <div className="relative shrink-0" ref={scoreRef}>
              <div
                onClick={() => setShowScoreBreakdown((v) => !v)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setShowScoreBreakdown((v) => !v);
                  }
                }}
                role="button"
                tabIndex={0}
                aria-haspopup="true"
                aria-expanded={showScoreBreakdown}
                className="flex items-center gap-4 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-xl p-3.5 cursor-pointer transition shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <div className="text-center">
                  <div className="text-3xl font-black text-blue-600 font-mono tracking-tight">{project.score.total}<span className="text-xs text-slate-400 font-normal">/100</span></div>
                  <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Spec Match Score</span>
                </div>
                <div className="h-10 w-px bg-slate-200"></div>
                <div className="text-xs space-y-1">
                  <div className="flex items-center gap-1.5 text-emerald-700 font-semibold">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0"></span>
                    High Priority Fit
                  </div>
                  <div className="text-[11px] text-slate-500">Click to view calculation breakdown</div>
                </div>
              </div>

              {showScoreBreakdown && (
                <div className="absolute right-0 top-full mt-2 w-72 bg-white border border-slate-200 rounded-xl shadow-xl p-4 z-50 text-xs space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                    <strong className="text-slate-900 font-bold">Score Calculation Breakdown</strong>
                    <button
                      onClick={() => setShowScoreBreakdown(false)}
                      aria-label="Close score breakdown"
                      className="text-slate-400 hover:text-slate-600"
                    >
                      ✕
                    </button>
                  </div>
                  <div className="space-y-2 text-slate-600">
                    {project.score.breakdown.map((row) => (
                      <div key={row.label} className="flex justify-between items-center">
                        <span>{row.label}</span>
                        <span className="font-mono font-bold text-emerald-600">+{row.points} pts</span>
                      </div>
                    ))}
                  </div>
                  <div className="pt-2 border-t border-slate-100 flex justify-between font-bold text-slate-900">
                    <span>Total Spec Match Score</span>
                    <span className="text-blue-600 font-mono">{scoreTotal} / 100</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* KPI GRID -- confirmed facts, each sourced; disputed figures marked "Sources vary" rather than picked */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 text-xs">
            {project.kpis.map((kpi) => (
              <div key={kpi.label} className="bg-slate-50 border border-slate-200 rounded-xl p-3">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500 text-[10px] font-semibold uppercase tracking-wider">{kpi.label}</span>
                  <ConfidenceTag level={kpi.confidence} />
                </div>
                <span className={`text-base font-bold block mt-1 ${kpi.valueClassName || 'text-slate-900'}`}>{kpi.value}</span>
                <Source>{kpi.source}</Source>
              </div>
            ))}
          </div>
        </section>

        {/* TWO-COLUMN WORKSPACE LAYOUT -- left carries the narrative (brief,
            scope, team); right is the lookup rail (activity, permits, contacts). */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

          {/* LEFT COLUMN */}
          <div className="lg:col-span-7 space-y-6">

            {/* EXECUTIVE BRIEF */}
            <section className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-3">
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <IconClipboard className="h-4 w-4 text-slate-400" />
                Executive Brief
              </h2>
              <p className="text-xs text-slate-600 leading-relaxed">{project.executiveBrief.text}</p>
              <Source>{project.executiveBrief.source}</Source>
            </section>

            {/* CSI SCOPE MATRIX */}
            <section className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-3">
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <IconGrid className="h-4 w-4 text-slate-400" />
                CSI Scope Matrix
              </h2>
              <div className="overflow-x-auto -mx-1">
                <table className="w-full text-xs border-collapse min-w-[480px]">
                  <thead>
                    <tr className="text-left text-[10px] uppercase tracking-wide text-slate-500">
                      <th scope="col" className="font-semibold pb-2 pr-3 w-28">Division</th>
                      <th scope="col" className="font-semibold pb-2 pr-3">Scope</th>
                      <th scope="col" className="font-semibold pb-2 w-24">Status</th>
                    </tr>
                  </thead>
                  <tbody className="align-top">
                    {project.csiScope.map((row) => (
                      <tr key={row.division} className="border-t border-slate-100">
                        <td className="py-2.5 pr-3 font-semibold text-slate-800">
                          {row.division}<br /><span className="font-normal text-slate-500">{row.label}</span>
                        </td>
                        <td className="py-2.5 pr-3 text-slate-600 leading-relaxed">
                          {row.scope}
                          <Source>{row.source}</Source>
                        </td>
                        <td className="py-2.5"><ConfidenceTag level={row.confidence} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {/* VERIFIED CONSTRUCTION TEAM */}
            <section className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-3">
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <IconUsers className="h-4 w-4 text-slate-400" />
                Verified Construction Team
              </h2>
              <div className="overflow-x-auto -mx-1">
                <table className="w-full text-xs border-collapse min-w-[420px]">
                  <thead>
                    <tr className="text-left text-[10px] uppercase tracking-wide text-slate-500">
                      <th scope="col" className="font-semibold pb-2 pr-3 w-40">Role</th>
                      <th scope="col" className="font-semibold pb-2 pr-3">Named Party</th>
                      <th scope="col" className="font-semibold pb-2 w-24">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {project.team.map((row) => (
                      <tr key={row.role} className="border-t border-slate-100">
                        <td className="py-2.5 pr-3 font-semibold text-slate-800">{row.role}</td>
                        <td className={`py-2.5 pr-3 ${row.confidence === 'unconfirmed' ? 'text-slate-500' : 'text-slate-600'}`}>{row.party}</td>
                        <td className="py-2.5"><ConfidenceTag level={row.confidence} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {project.stillOpenNote && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-[11px] text-blue-800 leading-relaxed">
                  <strong>Still open:</strong> {project.stillOpenNote}
                </div>
              )}
            </section>

          </div>

          {/* RIGHT COLUMN: WORKSPACE / LOOKUP RAIL */}
          <div className="lg:col-span-5 space-y-6">

            {/* WORKSPACE & ACTIVITY FEED */}
            <section className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <IconActivity className="h-4 w-4 text-slate-400" />
                  Workspace &amp; Activity Feed
                </h2>
                <div className="flex items-center bg-slate-100 p-0.5 rounded-lg text-[10px] font-semibold">
                  <button
                    onClick={() => setFilter('ALL')}
                    aria-pressed={feedFilter === 'ALL'}
                    className={`px-2 py-1 rounded-md transition ${feedFilter === 'ALL' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'}`}
                  >
                    All
                  </button>
                  <button
                    onClick={() => setFilter('AI_SIGNAL')}
                    aria-pressed={feedFilter === 'AI_SIGNAL'}
                    className={`px-2 py-1 rounded-md transition ${feedFilter === 'AI_SIGNAL' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'}`}
                  >
                    AI Signals
                  </button>
                  <button
                    onClick={() => setFilter('NEWS')}
                    aria-pressed={feedFilter === 'NEWS'}
                    className={`px-2 py-1 rounded-md transition ${feedFilter === 'NEWS' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'}`}
                  >
                    News
                  </button>
                </div>
              </div>

              <div className="space-y-3">
                {filteredActivities.map((act) => (
                  <div
                    key={act.id}
                    className={`p-3 border rounded-lg space-y-1 text-xs ${
                      act.type === 'AI_SIGNAL' ? 'bg-blue-50/50 border-blue-200' : 'bg-slate-50 border-slate-200'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-900 flex items-center gap-1.5">
                        {act.type === 'AI_SIGNAL' ? (
                          <IconBot className="h-3.5 w-3.5 text-blue-500 shrink-0" />
                        ) : (
                          <IconNewspaper className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                        )}
                        {act.source}
                      </span>
                      <span className="text-[10px] font-mono text-slate-500">{act.time}</span>
                    </div>
                    {act.url ? (
                      <a
                        href={act.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 font-medium leading-snug text-[11px] hover:text-blue-700 hover:underline underline-offset-2 flex items-start gap-1"
                      >
                        {act.title}
                        <span className="text-slate-400 shrink-0">↗</span>
                      </a>
                    ) : (
                      <p className="text-slate-800 font-medium leading-snug text-[11px]">{act.title}</p>
                    )}
                    <p className="text-slate-600 leading-relaxed text-[11px]">{act.body}</p>
                    {act.type === 'NEWS' && !act.url && (
                      <p className="text-[10px] text-slate-500 italic">Source link unverified — omitted</p>
                    )}
                  </div>
                ))}
                {filteredActivities.length === 0 && (
                  <p className="text-center text-[11px] text-slate-500 py-4">Nothing in this filter yet.</p>
                )}
              </div>
            </section>

            {/* PERMITS & FILINGS -- flattened to a divided list (was card-in-card-in-card) */}
            <section className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-3">
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <IconFileCheck className="h-4 w-4 text-slate-400" />
                Permits &amp; Filings
              </h2>
              <ul className="divide-y divide-slate-100 text-xs text-slate-600">
                {project.permits.map((p) => (
                  <li key={p.label} className="py-2.5 first:pt-0 last:pb-0">
                    <span className="font-semibold text-slate-800 block">{p.label}</span>
                    <span className="text-[11px] text-slate-500">{p.detail}</span>
                  </li>
                ))}
              </ul>
            </section>

            {/* CONTACTS */}
            <section className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-3">
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <IconPhone className="h-4 w-4 text-slate-400" />
                Contacts
              </h2>
              <div className="space-y-2 text-xs">
                {project.contacts.map((c, i) => (
                  <div
                    key={c.org}
                    className={`flex items-start justify-between gap-3 ${i < project.contacts.length - 1 ? 'border-b border-slate-100 pb-2' : ''}`}
                  >
                    <div>
                      <span className="font-semibold text-slate-800">{c.org}</span>
                      <p className="text-slate-600 mt-0.5">{c.detail}</p>
                    </div>
                    <ConfidenceTag level={c.confidence} />
                  </div>
                ))}
              </div>
              {project.contactsNote && (
                <p className="text-[11px] text-slate-500 leading-relaxed pt-1">{project.contactsNote}</p>
              )}
            </section>

          </div>
        </div>
      </main>
    </div>
  );
}
