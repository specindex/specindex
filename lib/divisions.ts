import type { Project } from "./types";
import { isStillOpen } from "./stats";

/**
 * Segmentation runs on CSI MasterFormat divisions rather than contractor trades.
 * Specifications are written division by division, so a manufacturer's product
 * lives in a division whether or not anyone calls it that. Trade labels also
 * overlap at different levels: "lighting" sits inside Division 26 alongside
 * switchgear, so treating the two as peers double counts the same buyer.
 */
export type Division = {
  code: string;
  /** MasterFormat division title. */
  name: string;
  /** How a rep would describe their own product line. */
  plain: string;
  /** Who typically writes this division into the spec. */
  specifiedBy: string;
  /** Category keywords as they appear in project records. */
  keywords: string[];
  /** URL-safe identifier for /projects/[state]/[trade]/ pSEO hub pages. */
  slug: string;
};

export const DIVISIONS: Division[] = [
  {
    code: "23",
    name: "HVAC",
    plain: "Heating, cooling, ventilation, chillers, VRF",
    specifiedBy: "Mechanical engineer",
    keywords: ["hvac", "cooling", "chiller", "refrigeration", "ventilation", "heat pump", "vrf", "ptac", "air handling", "lab air", "filtration", "boiler"],
    slug: "hvac",
  },
  {
    code: "26",
    name: "Electrical",
    plain: "Lighting, switchgear, generators, distribution",
    specifiedBy: "Electrical engineer",
    keywords: ["switchgear", "lighting", "generator", "electrical", "ups", "substation", "transformer", "power", "battery storage", "solar", "ev charging", "electrification", "grid interconnection", "trackers"],
    slug: "electrical",
  },
  {
    code: "08",
    name: "Openings",
    plain: "Glazing, curtain wall, storefront, doors, hardware",
    specifiedBy: "Architect",
    keywords: ["glazing", "curtain wall", "storefront", "window", "door", "hardware", "entry systems", "hangar door"],
    slug: "openings",
  },
  {
    code: "07",
    name: "Thermal and Moisture Protection",
    plain: "Roofing, insulation, EIFS, cladding, waterproofing",
    specifiedBy: "Architect or roofing consultant",
    keywords: ["roofing", "insulation", "eifs", "cladding", "waterproof", "coating", "corrosion", "storm-resistant"],
    slug: "roofing-thermal-moisture",
  },
  {
    code: "14",
    name: "Conveying Equipment",
    plain: "Elevators, escalators, conveyors, cranes",
    specifiedBy: "Architect with elevator consultant",
    keywords: ["elevator", "conveyor", "crane", "material handling", "escalator"],
    slug: "conveying-equipment",
  },
  {
    code: "21",
    name: "Fire Suppression",
    plain: "Sprinklers, ESFR, deluge, fire protection",
    specifiedBy: "Fire protection engineer",
    keywords: ["fire suppression", "fire protection", "sprinkler", "esfr", "deluge", "fire/life safety", "fire safety"],
    slug: "fire-suppression",
  },
  {
    code: "11",
    name: "Equipment",
    plain: "Dock equipment, lab, medical, kitchen, process",
    specifiedBy: "Owner with specialty consultant",
    keywords: ["dock", "lab equipment", "medical equipment", "kitchen equipment", "foodservice", "commercial kitchen", "process equipment", "imaging", "robotics", "stamping", "bottling", "packaging", "laundry", "store fixtures", "racking", "therapy equipment", "dental", "or systems", "industrial furnaces", "fuel systems", "tank farm", "dredging", "arena seating", "seating systems", "sports surfaces", "turf"],
    slug: "equipment",
  },
  {
    code: "09",
    name: "Finishes",
    plain: "Flooring, ceilings, drywall, paint, casework",
    specifiedBy: "Architect or interior designer",
    keywords: ["flooring", "ceiling", "finishes", "drywall", "paint", "acoustic", "fit-out", "build-out", "tenant improvement", "epoxy", "casework", "cabinetry", "countertops", "interior finishes"],
    slug: "finishes",
  },
  {
    code: "22",
    name: "Plumbing",
    plain: "Fixtures, piping, medical gas, water systems",
    specifiedBy: "Plumbing engineer",
    keywords: ["plumbing", "medical gas", "water systems", "water/sewer", "water/wastewater", "high-purity piping", "plumbing risers", "bathroom fixtures", "compressed air"],
    slug: "plumbing",
  },
  {
    code: "03",
    name: "Concrete",
    plain: "Cast in place, precast, tilt-up",
    specifiedBy: "Structural engineer",
    keywords: ["concrete", "tilt-up", "tilt-wall", "precast"],
    slug: "concrete",
  },
  {
    code: "31",
    name: "Earthwork",
    plain: "Site work, utilities, stormwater, drainage",
    specifiedBy: "Civil engineer",
    keywords: ["site work", "site civil", "site utilities", "site infrastructure", "civil infrastructure", "earthwork", "pad-ready", "site amenities", "stormwater", "drainage"],
    slug: "earthwork",
  },
  {
    code: "27",
    name: "Communications",
    plain: "Structured cabling, AV, nurse call, automation",
    specifiedBy: "Technology consultant",
    keywords: ["structured cabling", "av systems", "av/conference", "avl technology", "nurse call", "bms", "building automation", "process controls", "quality control systems", "smart-home", "smart access"],
    slug: "communications",
  },
  {
    code: "12",
    name: "Furnishings",
    plain: "FF&E, casegoods, window treatments",
    specifiedBy: "Interior designer or owner",
    keywords: ["ff&e", "furnishing", "casegoods", "window treatment", "site furnishings", "museum fit", "exhibit"],
    slug: "furnishings",
  },
  {
    code: "32",
    name: "Exterior Improvements",
    plain: "Paving, hardscape, fencing, landscape",
    specifiedBy: "Civil or landscape architect",
    keywords: ["paving", "hardscape", "fencing", "landscap", "barriers", "guardrail", "traffic systems", "road construction", "site lighting", "site/landscape"],
    slug: "exterior-improvements",
  },
  {
    code: "13",
    name: "Special Construction",
    plain: "Cleanrooms, shielding, modular, pools",
    specifiedBy: "Specialty consultant",
    keywords: ["cleanroom", "clean room", "bsl-3", "radiation shielding", "shielding", "modular construction", "prefab", "data center shells", "pool"],
    slug: "special-construction",
  },
  {
    code: "05",
    name: "Metals",
    plain: "Structural steel, metal framing, piling",
    specifiedBy: "Structural engineer",
    keywords: ["structural steel", "metal studs", "metal building", "specialty metals", "piling", "marine piling"],
    slug: "metals",
  },
  {
    code: "28",
    name: "Electronic Safety and Security",
    plain: "Access control, surveillance, fire alarm",
    specifiedBy: "Security consultant",
    keywords: ["security", "access control", "fire alarm"],
    slug: "electronic-safety-security",
  },
  {
    code: "33",
    name: "Utilities",
    plain: "Utility power, gas, process utilities",
    specifiedBy: "Civil engineer",
    keywords: ["utility power", "utility systems", "process utilities", "process piping"],
    slug: "utilities",
  },
  {
    code: "04",
    name: "Masonry",
    plain: "Brick, block, stone",
    specifiedBy: "Architect",
    keywords: ["masonry", "brick"],
    slug: "masonry",
  },
  {
    code: "10",
    name: "Specialties",
    plain: "Signage, lockers, partitions",
    specifiedBy: "Architect",
    keywords: ["signage", "locker", "partition"],
    slug: "specialties",
  },
];

export function divisionBySlug(slug: string): Division | undefined {
  return DIVISIONS.find((d) => d.slug === slug);
}

/**
 * First matching division for a raw category string, or null.
 *
 * Order of DIVISIONS is significant. Around 29 category strings in the corpus
 * match two divisions ("dock doors" hits both 08 and 11, "concrete/paving" hits
 * both 03 and 32), and the earlier entry claims them. Reordering the array will
 * move counts between divisions.
 */
function divisionForCategory(category: string): Division | null {
  const c = category.toLowerCase();
  for (const d of DIVISIONS) {
    if (d.keywords.some((k) => c.includes(k))) return d;
  }
  return null;
}

export type DivisionRollup = Division & {
  /** Distinct projects needing this division. */
  projects: number;
  /** Of those, how many are still in planning or permitting. */
  stillOpen: number;
};

/**
 * Distinct project counts per division. A project needing both cooling and
 * HVAC counts once against Division 23, not twice.
 */
export function getDivisionRollup(projects: Project[]): DivisionRollup[] {
  const buckets = new Map<string, Set<number>>();
  projects.forEach((p, i) => {
    for (const cat of p.competitor_watch) {
      const d = divisionForCategory(cat);
      if (!d) continue;
      if (!buckets.has(d.code)) buckets.set(d.code, new Set());
      buckets.get(d.code)!.add(i);
    }
  });

  return DIVISIONS.map((d) => {
    const idx = buckets.get(d.code) ?? new Set<number>();
    return {
      ...d,
      projects: idx.size,
      stillOpen: [...idx].filter((i) => isStillOpen(projects[i])).length,
    };
  })
    .filter((d) => d.projects > 0)
    .sort((a, b) => b.projects - a.projects);
}

/** How many projects map to at least one division. */
export function getMappedProjectCount(projects: Project[]): number {
  return projects.filter((p) =>
    p.competitor_watch.some((c) => divisionForCategory(c) !== null),
  ).length;
}

/** Projects whose competitor_watch includes at least one category mapping to this division. */
export function getProjectsForDivision(projects: Project[], division: Division): Project[] {
  return projects.filter((p) =>
    p.competitor_watch.some((c) => divisionForCategory(c)?.code === division.code),
  );
}
