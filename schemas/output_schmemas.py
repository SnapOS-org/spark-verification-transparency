from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ContradictionStatus(str, Enum):
    """Lifecycle state exposed to downstream consumers."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"


# --- NEW: Verification transparency ---


class VerificationStage(BaseModel):
    """Rating and reasoning at one stage of the verification pipeline."""

    stage: str = Field(
        description="Pipeline stage that produced this assessment: 'screener', 'checker', or 'verifier'.",
    )
    rating: int = Field(
        ge=0,
        le=100,
        description="Severity rating assigned at this stage (0 = no concern, 100 = critical).",
    )
    reasoning: str = Field(
        description="Rationale for the rating at this stage.",
    )


class ClaimProvenance(str, Enum):
    """Source type of the content underlying an occurrence."""

    ORIGINAL_TEXT = "original_text"
    LLM_TABLE_EXTRACTION = "llm_table_extraction"
    LLM_IMAGE_SUMMARY = "llm_image_summary"
    LLM_DESCRIPTION = "llm_description"


# --- END NEW ---


class Occurrence(BaseModel):
    """One document-local occurrence supporting a contradiction."""

    model_config = ConfigDict(populate_by_name=True)

    document_id: str = Field(
        alias="documentId",
        description="Identifier of the document containing the claim.",
    )
    document_name: str | None = Field(
        alias="documentName",
        description="Human-readable title of the document.",
    )
    content_excerpt: str = Field(
        alias="contentExcerpt",
        description="Text excerpt illustrating the contradiction.",
    )
    contradiction: str = Field(
        description="Description of the contradiction identified in this occurrence."
    )
    page_number: int | None = Field(
        default=None,
        alias="pageNumber",
        description="Page number where the excerpt appears, if available.",
    )

    # --- NEW: Provenance tracking ---
    provenance: ClaimProvenance = Field(
        default=ClaimProvenance.ORIGINAL_TEXT,
        description=(
            "Source type of this occurrence: original document text or "
            "LLM-generated content (table extraction, image summary)."
        ),
    )
    # --- END NEW ---


class Contradiction(BaseModel):
    """Top-level contradiction entity produced for one clustered inconsistency."""

    id: str = Field(description="Workflow-generated unique contradiction identifier.")
    title: str = Field(
        description=(
            "Short title summarizing the contradiction, ideally in a way that is "
            "understandable even without reading the full explanation."
        )
    )
    description: str = Field(
        description="Detailed contradiction explanation from the cluster summarizer."
    )
    status: ContradictionStatus = Field(
        description="Current lifecycle state of this contradiction."
    )
    occurrences: list[Occurrence] = Field(
        default_factory=list,
        description="Concrete document occurrences supporting this contradiction.",
    )

    # --- NEW: Verification transparency ---
    final_rating: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Final severity rating after all verification stages (verifier output).",
    )
    verification_chain: list[VerificationStage] = Field(
        default_factory=list,
        description=(
            "Rating and reasoning at each pipeline stage (screener -> checker -> verifier). "
            "Makes the progressive filtering visible to the Sachbearbeiter."
        ),
    )
    interpretation_assumption: str | None = Field(
        default=None,
        description=(
            "Key assumption underlying this finding. If this assumption does not hold, "
            "the finding may not apply. Surfaced from the screener/checker reasoning."
        ),
    )
    # --- END NEW ---


class DocumentOutput(BaseModel):
    """Document-level output payload uploaded as the temporal checkpoint."""

    contradictions: list[Contradiction] = Field(
        description="Contradictions identified for the processed document."
    )
