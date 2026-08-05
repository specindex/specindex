"""Model routing for the 11-step pipeline: Flash for discovery, Pro for extraction.

The split follows from what each model is actually good at, measured on this
project rather than assumed:

  FLASH -- generation and triage. Cheap, fast, and adequate where a WRONG
  answer is caught downstream. Discovery (step 1) is the clearest case: Flash
  proposes candidate portals and agency ids, and step 2's live curl/Playwright
  probe catches every fabrication. Measured accuracy on live network facts was
  1 of 7, which sounds disqualifying and is not -- provided the verification
  gate exists. Flash is a candidate generator whose errors are free.

  PRO -- extraction and reasoning, where a wrong answer is NOT caught
  downstream because there is nothing after it to catch anything. Parsing
  MasterFormat divisions, deciding basis-of-design vs listed alternate vs
  absent, and reading the procedural language of an addendum ("approved as
  noted, provided capacity is verified") are all cases where the output IS the
  product. A substitution ruling names a real company; getting it wrong is
  commercially damaging and no later step will notice.

The rule in one line: **Flash where a verifier follows, Pro where the output
is the product.**

WHERE THIS DELIBERATELY DIVERGES FROM THE ROUTING AS SPECIFIED. Step 8
document classification is routed to Flash ONLY as a fallback. The primary
classifier is `document_classifier.py` -- regex over filename plus first-page
text -- because it is free, deterministic, and instant across tens of
thousands of documents, where an LLM call per document would cost real money
and add latency for no accuracy gain on the easy majority. Flash is called
only when the deterministic classifier returns UNKNOWN on both filename and
page text. Spending a model call to decide that `AMEND0005_...pdf` is an
amendment would be waste.
"""
from __future__ import annotations

FLASH = "flash"
PRO = "pro"

# step -> tier, with the reason each choice is defensible.
STEP_TIER: dict[int, tuple[str, str]] = {
    1:  (FLASH, "discovery: candidate portals/agency ids; step 2's live probe catches fabrications"),
    2:  (FLASH, "live verification is curl/Playwright, not a model; Flash only summarises"),
    3:  (FLASH, "feedback loop bookkeeping"),
    4:  (FLASH, "institutional memory writes"),
    5:  (FLASH, "provider wiring is deterministic config"),
    6:  (PRO,   "grounded research fallback: strict schema compliance when cross-checking facts"),
    7:  (FLASH, "dedup gate is deterministic"),
    8:  (FLASH, "document classification -- FALLBACK ONLY, after document_classifier.py returns UNKNOWN"),
    9:  (PRO,   "spec-book extraction: MasterFormat division parsing, basis-of-design"),
    10: (PRO,   "spec position: basis of design / listed alternate / absent -- the product itself"),
    11: (PRO,   "substitution ledger: dense procedural addenda language, named third parties"),
}


def model_for_step(step: int, settings) -> str:
    tier, _ = STEP_TIER.get(step, (FLASH, "default"))
    return settings.pro_model if tier == PRO else settings.flash_model


def tier_for_step(step: int) -> str:
    return STEP_TIER.get(step, (FLASH, ""))[0]


def explain(step: int) -> str:
    tier, why = STEP_TIER.get(step, (FLASH, "default"))
    return f"step {step}: {tier.upper()} -- {why}"
