# SPARK — Technischer Hintergrund und Workflow-Übersicht

*Vorbereitung für den SPARK-Hackathon, 30. Juni / 1. Juli 2026*

---

## 1. Was ist SPARK?

SPARK steht für „Schnellere Planung und Realisierung durch KI." Es ist ein Open-Source-Projekt des Bundesministeriums für Digitales und Staatsmodernisierung (BMDS). Ziel: KI-gestützte Assistenz für Verwaltungssachbearbeitende bei der Prüfung von Genehmigungsanträgen — insbesondere Planfeststellungsverfahren (Windkraft, Infrastruktur, Bauvorhaben).

**Lizenz:** EUPL-1.2 (European Union Public License)
**Repository:** gitlab.opencode.de/bmds/planungs-und-genehmigungsbeschleunigung
**Sprache:** Python 3.13
**Status:** Release 1 (Beta, seit April 2026)

---

## 2. Welche LLMs werden verwendet?

**Entscheidend: SPARK nutzt ausschließlich selbst gehostete Open-Source-Modelle.** Keine Daten gehen an OpenAI, Anthropic oder andere Cloud-Anbieter. Das ist eine souveräne Architektur — passend für Behördendaten.

### Die drei Modelle

| Modell | Typ | Parameter | Funktion |
|--------|-----|-----------|----------|
| **gpt-oss-120b** | Open-Source LLM | ~120 Mrd. | Hauptmodell für alle Textanalysen: Claim-Extraktion, Risikobewertung, Kontextprüfung, Verifikation, Zusammenfassung |
| **Mistral-Small-24B-Instruct** | Mistral Open-Source | 24 Mrd. | Alternatives/ergänzendes Modell (leichter, schneller) |
| **BAAI/bge-m3** | Embedding-Modell | — | Mehrsprachige Vektorisierung für semantische Suche in Qdrant |

### Wie werden sie betrieben?

```
Alle Modelle laufen auf vLLM (GPU-basierter Inference-Server)
         │
         ▼
    LiteLLM Proxy (OpenAI-kompatible API)
         │
         ▼
    SPARK-Module greifen per OpenAI-SDK darauf zu
```

- **vLLM:** Hochperformanter Inference-Server, self-hosted
- **LiteLLM:** Proxy-Server, der verschiedene Modelle über eine einheitliche OpenAI-kompatible API bereitstellt
- **Konfiguration:** Temperature 0.0 (deterministisch), max. 15.000 Tokens, Structured Outputs (Pydantic-Schemas als response_format)

**Wichtig für den Hackathon:** Du arbeitest nicht mit einer Cloud-API. Das Modell läuft lokal im BMDS-Netzwerk. Die Qualität der Ergebnisse hängt direkt von den Prompts ab — nicht vom Modell-Provider.

---

## 3. Infrastruktur-Stack

```
┌─────────────────────────────────────────────────┐
│                    FRONTEND                      │
│            (Benutzeroberfläche)                  │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│          AGENT ORCHESTRATION SERVICE             │
│     (FastAPI — steuert den Gesamtworkflow)      │
└────────────────────┬────────────────────────────┘
                     │
        ┌────────────┼────────────────┐
        │            │                │
        ▼            ▼                ▼
┌──────────┐  ┌──────────────┐  ┌──────────────┐
│ Temporal  │  │  PostgreSQL  │  │    MinIO      │
│ (Workflow │  │  (Metadaten, │  │  (Dokumente,  │
│  Engine)  │  │   Projekte)  │  │   Berichte)   │
└──────────┘  └──────────────┘  └──────────────┘
        │
        ├──── Qdrant (Vektordatenbank für Claims)
        │
        ├──── LiteLLM Proxy → vLLM (LLM-Modelle)
        │
        └──── Prompt Injection Defense (Shared Service)
```

### Komponenten im Detail

| Komponente | Technologie | Funktion |
|-----------|-------------|----------|
| **Workflow Engine** | Temporal | Orchestriert alle Pipeline-Schritte mit Retries, Timeouts, State Management |
| **Vektordatenbank** | Qdrant | Speichert Claim-Embeddings für semantische Ähnlichkeitssuche |
| **Objektspeicher** | MinIO | Speichert hochgeladene Dokumente und generierte Berichte |
| **Datenbank** | PostgreSQL | Projekt-Metadaten, Konfiguration, Ergebnisse |
| **LLM-Zugang** | LiteLLM + vLLM | OpenAI-kompatible API auf selbst gehostete Open-Source-Modelle |
| **Containerisierung** | Docker Compose | Alle Services als Container orchestriert |
| **Prompt-Schutz** | Eigener Shared Service | Regex-basiertes Pattern-Stripping, Unicode-Bereinigung, Tag-Sandboxing |

---

## 4. Der Workflow: Was passiert Schritt für Schritt?

### Aktueller Workflow (Release 1)

```
SACHBEARBEITER lädt Antragsunterlagen hoch (PDF/DOCX)
         │
         ▼
┌─────────────────────────────────────────────────────┐
│  SCHRITT 1: INHALTSEXTRAKTION                       │
│                                                      │
│  • PDF/DOCX-Parsing (Text, Tabellen, Bilder)        │
│  • Chunking (Textabschnitte bilden)                  │
│  • Tabellen → LLM extrahiert strukturierte Daten     │
│  • Bilder → Vision-LLM erstellt Zusammenfassungen    │
│  • Embeddings generieren (BAAI/bge-m3)               │
│  • Alles in Qdrant + MinIO speichern                 │
│                                                      │
│  ⚠ HIER ENTSTEHT DER ERSTE INTERPRETATIONSSCHRITT:  │
│  LLM-Zusammenfassungen von Bildern/Tabellen sind     │
│  Interpretationen, keine Originaldaten.              │
└────────────────────┬────────────────────────────────┘
                     │
        ┌────────────┴────────────────┐
        │                             │
        ▼                             ▼
┌───────────────────┐   ┌───────────────────────────┐
│ SCHRITT 2a:       │   │ SCHRITT 2b:               │
│ FORMALE PRÜFUNG   │   │ INHALTSVERZEICHNIS-       │
│                   │   │ MATCHING                  │
│ • Dokument-       │   │                           │
│   zusammenfassung │   │ • Chunks klassifizieren   │
│ • Klassifikation  │   │ • Globales               │
│ • Vollständig-    │   │   Inhaltsverzeichnis     │
│   keitsprüfung    │   │   erkennen               │
│                   │   │ • Dokumenttypen           │
│ Ergebnis: Welche  │   │   zuordnen               │
│ Dokumente fehlen? │   │                           │
└───────────────────┘   └───────────────────────────┘
        │
        │ Klassifikation → wird für Plausibilitätsprüfung gebraucht
        ▼
┌─────────────────────────────────────────────────────┐
│  SCHRITT 3: PLAUSIBILITÄTSPRÜFUNG                    │
│                                                      │
│  Phase A: Claim-Extraktion                           │
│  ┌─────────────────────────────────────────────────┐ │
│  │ • Aus jedem Chunk werden Behauptungen (Claims)  │ │
│  │   extrahiert                                    │ │
│  │ • Tabellendaten werden zeilenweise extrahiert   │ │
│  │ • Alle Claims als Vektoren in Qdrant gespeichert│ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  Phase B: Prüflogik (3-stufig)                       │
│  ┌─────────────────────────────────────────────────┐ │
│  │                                                 │ │
│  │  STUFE 1: RISK SCREENER                         │ │
│  │  • Vergleicht Claim-Paare                       │ │
│  │  • Vergibt Rating (0-100)                       │ │
│  │  • Generiert Arbeitsnotiz: „Prüfen, ob..."      │ │
│  │  • Strategie: lieber zu viel finden als zu wenig│ │
│  │  • ⚠ Rating = normative Entscheidung            │ │
│  │                                                 │ │
│  │        │ Paare mit Rating > 50                  │ │
│  │        ▼                                        │ │
│  │                                                 │ │
│  │  STUFE 2: CONTEXT CHECKER                       │ │
│  │  • Vollständiger Chunk-Vergleich mit Kontext    │ │
│  │  • Strenge False-Positive-Regeln (9 Stück)      │ │
│  │  • Grounding-Pflicht für hohe Ratings           │ │
│  │  • Explizite Marker-Pflicht für Widersprüche    │ │
│  │  • Rating (0-100)                               │ │
│  │                                                 │ │
│  │        │ bestätigte Konflikte                   │ │
│  │        ▼                                        │ │
│  │                                                 │ │
│  │  STUFE 3: CONFLICT VERIFIER                     │ │
│  │  • Audit des Context-Checker-Ergebnisses        │ │
│  │  • Prüft Auszug-Integrität                      │ │
│  │  • Prüft Grounding                              │ │
│  │  • Kann Rating SENKEN, nie ERHÖHEN              │ │
│  │  • Endgültiges Urteil                           │ │
│  │                                                 │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  Phase C: Cluster-Zusammenfassung                    │
│  • Verwandte Konflikte gruppieren                    │
│  • Menschenlesbare Zusammenfassung generieren        │
│                                                      │
│  ⚠ HIER GEHT DIE PRÜFKETTE VERLOREN:               │
│  Ratings, Begründungen und Herkunftsinfos            │
│  werden NICHT in die Endausgabe übernommen.          │
│                                                      │
│  Ausgabe: Plausibilitätsbericht (JSON → DMS)         │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│  SACHBEARBEITER SIEHT:                               │
│                                                      │
│  • Vollständigkeitsprüfung: welche Dokumente fehlen  │
│  • Dokumentklassifikation                            │
│  • Plausibilitätsfeststellungen mit Titel +           │
│    Beschreibung + Textstellen                        │
│                                                      │
│  SACHBEARBEITER SIEHT NICHT:                         │
│                                                      │
│  ✗ Kein Rating (wie sicher ist das System?)          │
│  ✗ Keine Begründung (warum wurde das geflaggt?)      │
│  ✗ Keine Prüfkette (Screener→Checker→Verifier)      │
│  ✗ Keine Herkunft (Originaltext vs. LLM-Zusammen-    │
│    fassung)                                          │
│  ✗ Keine Annahme (unter welcher Interpretation       │
│    gilt die Feststellung?)                           │
│                                                      │
│  ENTSCHEIDET: Genehmigung / Ablehnung / Nachforderung│
└─────────────────────────────────────────────────────┘
```

### Geplanter Workflow (Release 2 — Roadmap)

```
Alles von oben, PLUS:

┌─────────────────────────────────────────────────────┐
│  SCHRITT 4: RECHTLICHE PRÜFUNG UND BEWERTUNG        │
│  (noch nicht implementiert)                          │
│                                                      │
│  • Automatisierte Normendekonstruktion               │
│  • Abgleich mit Gesetzesdatenbanken                  │
│  • Juristische Bewertungsmechanismen                 │
│                                                      │
│  ⚠ Hier beginnt die Systeminterpretation von Recht.  │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│  SCHRITT 5: BESCHLUSSERSTELLUNG                      │
│  (noch nicht implementiert)                          │
│                                                      │
│  • System entwirft den Genehmigungsbescheid          │
│  • Sachbearbeiter „prüft" den vorgefertigten Text    │
│                                                      │
│  ⚠ KRITISCHSTER PUNKT (Oversight Compression):       │
│  Bei hohem Antragsvolumen und Zeitdruck wird die     │
│  „Prüfung" zur Unterschrift.                         │
└─────────────────────────────────────────────────────┘
```

---

## 5. Was das System richtig macht

| Stärke | Detail |
|--------|--------|
| **3-stufige Verifikation** | Screener → Checker → Verifier. Der Verifier kann Ratings nur senken, nie erhöhen. Das verhindert Eskalationsbias. |
| **9 False-Positive-Regeln** | Im Context Checker: keine semantische Eskalation, Grounding-Pflicht, explizite Marker-Pflicht, striktes Entity/Scope/Level-Matching. |
| **LLM-Zusammenfassungen markiert** | Im Prompt als „schwacher Hinweis" gekennzeichnet. Hohe Ratings brauchen Primärtext-Evidenz. |
| **Prompt-Injection-Schutz** | Externe Daten werden sanitisiert, getaggt und in Sandbox-Blöcke gewrappt. |
| **Souveräne Architektur** | Alle Modelle self-hosted via vLLM. Keine Daten verlassen die Infrastruktur. |
| **Deterministische Konfiguration** | Temperature 0.0 — reproduzierbare Ergebnisse. |

---

## 6. Was dem System fehlt (unser Hackathon-Beitrag)

| Lücke | Warum problematisch |
|-------|---------------------|
| **Kein Rating in der Endausgabe** | Der Sachbearbeiter weiß nicht, wie sicher das System bei einer Feststellung ist. Ein Rating-52-Widerspruch sieht genauso aus wie ein Rating-95-Widerspruch. |
| **Keine Prüfkette sichtbar** | Die dreistufige Verifikation (das stärkste Feature!) ist für den Sachbearbeiter unsichtbar. Er sieht nur das Endergebnis, nicht den Weg dorthin. |
| **Keine Herkunftskennzeichnung** | „Widerspruch" kann auf Originaltext oder auf einer LLM-Zusammenfassung einer Tabelle basieren. Der Sachbearbeiter kann das nicht unterscheiden. |
| **Kein menschlicher Breakpoint** | Die Pipeline läuft von Extraktion bis Plausibilitätsbericht ohne Unterbrechung. Extraktionsfehler werden zu „Widersprüchen." |
| **Ratings sind verdeckte Norminterpretation** | Der Screener sagt „keine normativen Entscheidungen" — aber ein Rating IST eine normative Entscheidung. |
| **Keine Entscheidungsgrenze für Release 2** | Wenn das System Beschlüsse entwirft, muss sichtbar sein, was das System formuliert hat und was der Sachbearbeiter festlegen muss. |

---

## 7. Vorher/Nachher (was wir am Hackathon bauen)

### VORHER (aktuell):
```json
{
  "title": "Widersprüchliche Angaben zur Flächennutzung",
  "description": "In Dokument A wird eine Fläche von 12,4 ha genannt, 
                  in Dokument B steht 11,8 ha.",
  "status": "OPEN",
  "occurrences": [
    {"document_name": "Umweltbericht.pdf", "content_excerpt": "...12,4 ha..."},
    {"document_name": "Planzeichnung.pdf", "content_excerpt": "...11,8 ha..."}
  ]
}
```

Der Sachbearbeiter sieht: „Es gibt einen Widerspruch." Mehr nicht.

### NACHHER (unser Beitrag):
```json
{
  "title": "Widersprüchliche Angaben zur Flächennutzung",
  "description": "In Dokument A wird eine Fläche von 12,4 ha genannt, 
                  in Dokument B steht 11,8 ha.",
  "status": "OPEN",
  "final_rating": 52,
  "verification_chain": [
    {"stage": "screener", "rating": 78, 
     "reasoning": "Zahlenwerte weichen ab: 12,4 ha vs. 11,8 ha."},
    {"stage": "checker", "rating": 65, 
     "reasoning": "Im vollständigen Kontext bestätigt sich die Abweichung."},
    {"stage": "verifier", "rating": 52, 
     "reasoning": "Rating reduziert: Unterschied könnte auf verschiedene 
                   Bezugsjahre zurückgehen."}
  ],
  "interpretation_assumption": "Setzt voraus, dass sich beide Werte auf 
    dasselbe Plangebiet beziehen. Falls unterschiedliche Teilflächen 
    gemeint sind, ist diese Feststellung nicht anwendbar.",
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

Der Sachbearbeiter sieht:
- **Wie sicher** das System ist (Rating ging von 78 → 65 → 52 — abnehmende Sicherheit)
- **Warum** es reduziert wurde (verschiedene Bezugsjahre möglich)
- **Woher** die Daten stammen (Originaltext vs. LLM-Extraktion aus Tabelle)
- **Welche Annahme** zugrunde liegt (gleiches Plangebiet)

**Ein Satz:** Das System findet dieselben Widersprüche. Aber jetzt kann der Sachbearbeiter beurteilen, wie ernst er sie nehmen muss.

---

## 8. Wird das akzeptiert?

Das ist die richtige Frage. Drei Gründe, warum es akzeptiert werden sollte:

**Erstens:** Wir ändern keine Architektur. Wir erweitern bestehende Pydantic-Schemas um Felder, die die Pipeline bereits intern generiert. Die Daten existieren — sie werden nur nicht durchgereicht.

**Zweitens:** Challenge 3 heißt „Safe and Stable!" Das BMDS definiert SPARK als „Assistenzsystem, das die Entscheidungsverantwortung nicht ersetzt." Unser Beitrag macht genau das überprüfbar: Er zeigt dem Sachbearbeiter, wo das System assistiert und wo es rahmt.

**Drittens:** Das BMDS weiß, dass Release 2 (Beschlusserstellung) kritisch wird. Ein Transparenz-Layer, der jetzt eingebaut wird, verhindert, dass die Beschlusserstellung später zum Oversight-Compression-Problem wird. Das ist präventive Governance — genau das, was der Hackathon fördern soll.

---

*Marko A. E. Chalupa | SnapOS Foundation | Mai 2026*
