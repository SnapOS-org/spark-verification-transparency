# SPARK Verification Transparency Layer

**Independent code contribution for the [SPARK Workflow](https://gitlab.opencode.de/bmds/planungs-und-genehmigungsbeschleunigung/spark-workflow) project by the German Federal Ministry for Digital and State Modernization (BMDS).**

---

## What This Is

SPARK is an open-source AI assistance system (EUPL-1.2) designed to help public administration staff review planning and permit applications. It includes a three-stage plausibility verification pipeline: Risk Screener → Context Checker → Conflict Verifier.

The pipeline is well-engineered. The verification stages generate ratings, reasoning, and provenance data at every step.

**None of it reaches the Sachbearbeiter.**

The final output contains a title, a description, and a status. No rating. No reasoning. No verification chain. No indication whether a finding is based on original document text or an LLM-generated summary of a table.

This repository contains four schema-level changes that carry the existing verification data through to the output — so that the person making the decision can see how confident the system is, why, and where the data came from.

---

## Why This Exists Here

SPARK is published as open source. Contributions would normally be submitted via the project's issue tracker or discussion forum.

- **Issue tracker:** Disabled on the repository.
- **Discussion forum:** Returns "this page does not exist or is private."
- **Hackathon (June 30 / July 1, 2026):** Application submitted before deadline. Confirmation of receipt received. Decision promised by June 14, 2026. No response received.

This repository exists because there is currently no channel to contribute to an open-source project that has closed all contribution channels.

The code is published here so it can be reviewed, referenced, and — if the upstream project chooses — adopted.

---

## The Four Changes

### 1. Verification Chain in Output Schema

**File:** `output_schemas.py` (replaces `check_logic_wf/schemas/output_schemas.py`)

Adds `VerificationStage` model, `final_rating`, `verification_chain`, and `interpretation_assumption` to the `Contradiction` output. Also adds `ClaimProvenance` enum and `provenance` field to `Occurrence`.

**Before:** Sachbearbeiter sees "Widerspruch gefunden."

**After:** Sachbearbeiter sees: "Screener rated 78 (reason), Checker confirmed at 65 (reason), Verifier reduced to 52 (reason). Based on original text vs. LLM table extraction. Key assumption: same planning area."

### 2. Claim Provenance Tracking

**File:** `qdrant_schemas.py` (replaces `qdrant/schemas.py`)

Adds `ClaimProvenance` enum and `provenance` field to `ClaimPayload`. Enables distinction between claims extracted from original document text and claims derived from LLM-generated content (table extractions, image summaries).

**Why:** The prompts already treat LLM-generated content as "weak hints." This distinction should survive into the output so the Sachbearbeiter can calibrate trust appropriately.

### 3. Ratings Through Clustering

**File:** `cluster_summarizer_schemas.py` (replaces `check_logic_wf/schemas/cluster_summarizer_schemas.py`)

Adds `screener_rating`, `checker_rating`, `verifier_rating`, and `screener_note` to `InconsistencyPair`. Prevents the verification history from being discarded during cluster summarization.

**Why:** The three-stage verification — where the verifier can lower ratings but never raise them — is one of SPARK's strongest architectural features. It should be visible in the output.

### 4. Decision Boundary Schema (Release 2 Preparation)

**File:** `decision_boundary.py` (new file for `check_logic_wf/schemas/`)

Introduces `DecisionOrigin` enum (`system_extracted`, `system_interpreted`, `requires_human_determination`) and `DecisionBoundaryReport` schema.

**Why:** The SPARK roadmap includes "Drafting of decisions" (Beschlusserstellung) in Release 2. When the system generates decision drafts, every element should be explicitly marked: extracted from documents, interpreted by the system, or requiring human determination. Building this into the schema before the feature is implemented is significantly easier than retrofitting it afterward.

**Reference:** For the governance rationale, see DIP Audit #8 — Oversight Compression in Automated Claims Processing (DOI: [10.5281/zenodo.20466843](https://doi.org/10.5281/zenodo.20466843)). A U.S. federal court found that allowing "an algorithm to make the decision so long as a medical director pushes the button" constituted an abuse of discretion (Kisting-Leung v. Cigna Corp., E.D. Cal., March 2025).

---

## Before / After

**Before (current SPARK output):**
```json
{
  "title": "Widersprüchliche Angaben zur Flächennutzung",
  "description": "In Dokument A wird...",
  "status": "OPEN",
  "occurrences": [...]
}
```

**After (with this contribution):**
```json
{
  "title": "Widersprüchliche Angaben zur Flächennutzung",
  "description": "In Dokument A wird...",
  "status": "OPEN",
  "final_rating": 52,
  "verification_chain": [
    {"stage": "screener", "rating": 78,
     "reasoning": "Zahlenwerte weichen ab: 12,4 ha vs. 11,8 ha."},
    {"stage": "checker", "rating": 65,
     "reasoning": "Im vollständigen Kontext bestätigt."},
    {"stage": "verifier", "rating": 52,
     "reasoning": "Rating reduziert: Unterschied könnte auf verschiedene Bezugsjahre zurückgehen."}
  ],
  "interpretation_assumption": "Assumes both values refer to the same planning area.",
  "occurrences": [
    {"document_name": "Umweltbericht.pdf",
     "content_excerpt": "...12,4 ha...",
     "provenance": "original_text"},
    {"document_name": "Planzeichnung_Tabelle.pdf",
     "content_excerpt": "...11,8 ha...",
     "provenance": "llm_table_extraction"}
  ]
}
```

The system finds the same contradictions. The Sachbearbeiter can now judge how seriously to take them.

---

## Technical Details

- **Language:** Python 3.13
- **Dependencies:** Pydantic v2 (BaseModel, Field, ConfigDict)
- **Compatibility:** All changes are additive. Existing fields are unchanged. New fields use `default` or `default_factory` — no breaking changes to downstream consumers.
- **Validation:** All files pass `ast.parse()` syntax check.

---

## Upstream Repository

- **Project:** [SPARK Workflow](https://gitlab.opencode.de/bmds/planungs-und-genehmigungsbeschleunigung/spark-workflow)
- **Organization:** BMDS (Bundesministerium für Digitales und Staatsmodernisierung)
- **License:** EUPL-1.2
- **Status:** Release 2 deployed (June 2026)

---

## Related Publications

| Publication | DOI |
|------------|-----|
| Decision Integrity Assessment: SPARK Workflow Pipeline | Included in this repository |
| Reconstructability as a Constitutive Property of Institutional Decision Integrity | [10.5281/zenodo.20579234](https://doi.org/10.5281/zenodo.20579234) |
| DIP Audit #8 — Oversight Compression: Cigna PxDx | [10.5281/zenodo.20466843](https://doi.org/10.5281/zenodo.20466843) |
| DIP Audit #7 — Governance Simulation: TD Bank AML | [10.5281/zenodo.20133694](https://doi.org/10.5281/zenodo.20133694) |
| DIP Audit #6 — Decision Identity Failure: UnitedHealth nH Predict | [10.5281/zenodo.19744184](https://doi.org/10.5281/zenodo.19744184) |
| GCCL v0.1 | [10.5281/zenodo.18362037](https://doi.org/10.5281/zenodo.18362037) |

---

## Author

**Marko A. E. Chalupa**
CTO & AI Architect
United Coding GmbH & Co. KG / SnapOS Foundation
audit@snapos.org · ORCID: [0009-0000-6493-4599](https://orcid.org/0009-0000-6493-4599)

---

## License

This contribution is published under [EUPL-1.2](LICENSE), matching the upstream project license.
