# SPARK Workflow Pipeline — Architecture Overview

*Based on source code analysis of spark-workflow-main (Release 1, March 2026)*

---

## 1. Infrastructure Layer

```
PostgreSQL ──── Persistent storage (projects, metadata, results)
MinIO ───────── Object storage (uploaded documents, generated reports)
Qdrant ──────── Vector database (document chunks, embeddings)
Temporal ────── Workflow orchestration engine (all pipelines)
LiteLLM ─────── LLM proxy (OpenAI-compatible API endpoint)
```

All services orchestrated via Docker Compose. Temporal manages workflow execution, retries, and state.

---

## 2. Full Pipeline (FVP Workflow)

```
                    ┌─────────────────────┐
                    │   Document Upload    │
                    │   (PDF / DOCX)       │
                    └──────────┬──────────┘
                               │
                               ▼
                ┌──────────────────────────────┐
                │   1. INHALTSEXTRAKTION        │
                │   (Content Extraction)        │
                │                              │
                │   • PDF/DOCX parsing         │
                │   • Text chunking            │
                │   • Table extraction (LLM)   │
                │   • Image analysis (VLM)     │
                │   • Embedding generation     │
                │   • Storage → Qdrant + MinIO │
                └──────────────┬───────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
    ┌───────────────────────┐  ┌────────────────────────────┐
    │ 2a. FORMALE PRÜFUNG   │  │ 2b. INHALTSVERZEICHNIS     │
    │ (Formal Check)        │  │     MATCHING               │
    │                       │  │ (ToC Matching)             │
    │ • Doc summarization   │  │                            │
    │ • Doc classification  │  │ • Chunk classification     │
    │ • Type matching       │  │ • Global ToC detection     │
    │ • Completeness check  │  │ • Document type matching   │
    │                       │  │   against ToC entries      │
    │ Output: Which docs    │  │                            │
    │ are present/missing   │  │ Output: Structured         │
    │ from required list    │  │ document inventory         │
    └───────────┬───────────┘  └────────────────────────────┘
                │
                │ classification_file_id
                ▼
    ┌───────────────────────────────────────────┐
    │ 3. PLAUSIBILITÄTSPRÜFUNG                  │
    │ (Plausibility Check)                      │
    │                                           │
    │ Phase A: Claim Extraction                 │
    │ ┌───────────────────────────────────────┐ │
    │ │ • Extract claims from each chunk      │ │
    │ │ • Generate text formulations          │ │
    │ │ • Extract table data                  │ │
    │ │ • Store as vectors in Qdrant          │ │
    │ └───────────────────┬───────────────────┘ │
    │                     │                     │
    │ Phase B: Check Logic                      │
    │ ┌───────────────────────────────────────┐ │
    │ │                                       │ │
    │ │ For each document:                    │ │
    │ │                                       │ │
    │ │ B1. RISK SCREENER                     │ │
    │ │     • Compare claim pairs             │ │
    │ │     • Assign rating (0-100)           │ │
    │ │     • Generate "Prüfen, ob..." note   │ │
    │ │     • recall-first approach            │ │
    │ │                                       │ │
    │ │           │ pairs with rating > 0     │ │
    │ │           ▼                           │ │
    │ │                                       │ │
    │ │ B2. CONTEXT CHECKER                   │ │
    │ │     • Full chunk comparison           │ │
    │ │     • Strict false-positive rules     │ │
    │ │     • Grounding requirement           │ │
    │ │     • Explicit marker requirement     │ │
    │ │     • Rating (0-100)                  │ │
    │ │                                       │ │
    │ │           │ rated conflicts           │ │
    │ │           ▼                           │ │
    │ │                                       │ │
    │ │ B3. CONFLICT VERIFIER                 │ │
    │ │     • Audit of Context Checker output │ │
    │ │     • Excerpt integrity check         │ │
    │ │     • Grounding verification          │ │
    │ │     • Can lower rating, never raise   │ │
    │ │     • Final verdict                   │ │
    │ │                                       │ │
    │ └───────────────────────────────────────┘ │
    │                                           │
    │ B4. CLUSTER SUMMARIZER                    │
    │     • Group related conflicts             │
    │     • Generate human-readable summary     │
    │                                           │
    │ Output: Plausibility report (JSON → DMS)  │
    └───────────────────────────────────────────┘
                    │
                    ▼
    ┌───────────────────────────────────────────┐
    │ SACHBEARBEITER (Human Decision)           │
    │                                           │
    │ Receives:                                 │
    │ • Completeness check results              │
    │ • Document classification                 │
    │ • Plausibility findings with ratings      │
    │ • Conflict summaries                      │
    │                                           │
    │ Decides: approve / reject / request more  │
    └───────────────────────────────────────────┘
```

---

## 3. Security Layer

```
Prompt Injection Defense (shared service):
  • Regex-based pattern stripping (ChatML, Llama, Gemini markers)
  • Unicode invisible character removal
  • Special character tagging (¤EXTERNAL_DATA¤)
  • Anti-injection preamble in all system prompts
  • Jinja2 sandbox for template rendering
  • External data wrapped in tagged blocks
```

---

## 4. Identified Decision Loops (DIP-relevant)

### Loop 1: Rating as hidden normative judgment

```
Document chunks → Risk Screener → Rating (0-100)
                                       │
                    "keine normativen   │  ← but rating IS
                     Entscheidungen"    │     a normative choice
                                       ▼
                              Sachbearbeiter sees:
                              "Rating 78 — prüfen"
                              
                              Does NOT see:
                              "System chose interpretation X
                               over alternatives Y, Z"
```

### Loop 2: No human breakpoint in pipeline

```
Extraction → Formal Check → Plausibility Check → Human
     │              │               │
     │    errors propagate forward  │
     │              │               │
     └──────────────┴───────────────┘
     
     No intermediate human checkpoint.
     Extraction errors become "contradictions"
     in the plausibility layer.
```

### Loop 3: LLM summaries as weak witnesses with strong effect

```
Image/Table → LLM Summary → Qdrant Vector → Plausibility Check
                  │                                │
                  │ marked as "weak hint"           │ treated as
                  │ in prompt instructions          │ comparable chunk
                  │                                 │
                  └─── provenance lost ─────────────┘
                  
     Sachbearbeiter cannot distinguish which
     "contradictions" are based on original text
     vs. LLM-generated summaries.
```

### Loop 4: Release 2 risk (not yet in code)

```
Current:  System extracts + checks → Human decides
Future:   System extracts + checks + drafts decision → Human reviews

     At scale: review becomes signature.
     This is the Oversight Compression pattern (DIP Audit #8).
```

---

## 5. What Exists vs. What Is Missing

| Exists | Missing |
|--------|---------|
| Three-stage verification (screener → checker → verifier) | Human breakpoint between pipeline stages |
| Explicit false-positive prevention rules | Provenance tracking (original vs. LLM-generated) visible to user |
| Prompt injection defense (regex + tagging) | Rating explanation showing which interpretation was chosen |
| "Can lower rating, never raise" constraint | Audit trail of interpretive choices per case |
| LLM summary marking in prompts | User-facing transparency about framing boundaries |

---

## 6. Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.13 |
| Workflow engine | Temporal |
| Vector DB | Qdrant |
| Object storage | MinIO |
| Database | PostgreSQL |
| LLM interface | LiteLLM (OpenAI-compatible) |
| Containerization | Docker Compose |
| Package management | uv |
| License | EUPL-1.2 |

---

*Analysis prepared for SPARK Hackathon Challenge 3 preparation.*
*Marko A. E. Chalupa | SnapOS Foundation | 2026-05-31*
