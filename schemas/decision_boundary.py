"""Decision Boundary Schema — Transparency layer for Release 2 (Beschlusserstellung).

Marks each element in a system-generated decision draft as:
- extracted (from source documents),
- interpreted (system judgment involved), or
- requiring human determination.

Purpose
-------
When SPARK generates decision drafts (Beschlüsse), the Sachbearbeiter must be
able to distinguish where the system's framing ends and their own judgment
begins.  This schema ensures that every element in a system-generated draft
carries an explicit origin marker — making the assistance boundary visible
even under operational scale and time pressure.

Reference
---------
For the governance rationale behind this schema, see:

    Chalupa, M. A. E. (2026). "Decision Integrity Assessment: SPARK Workflow
    Pipeline." SnapOS Foundation.

    Chalupa, M. A. E. (2026). "DIP Audit #8 — Oversight Compression in
    Automated Claims Processing: Cigna PxDx."
    DOI: 10.5281/zenodo.20466843

Note
----
This schema is introduced proactively — before the Beschlusserstellung module
is implemented — so that the transparency layer is architecturally expected
from the start, rather than retrofitted after the feature is built.
"""

from enum import Enum

from pydantic import BaseModel, Field


class DecisionOrigin(str, Enum):
    """Origin of one element in a system-generated decision draft.

    SYSTEM_EXTRACTED
        The element was directly extracted from a source document
        without interpretation.  The Sachbearbeiter can verify it
        against the original.

    SYSTEM_INTERPRETED
        The element involves system interpretation — e.g. a legal
        assessment, a norm application, or a plausibility judgment.
        The Sachbearbeiter should review the underlying assumption.

    REQUIRES_HUMAN_DETERMINATION
        The element cannot be resolved by the system.  It requires
        an explicit determination by the Sachbearbeiter — e.g. a
        discretionary judgment, a policy decision, or a case-specific
        assessment that exceeds the system's mandate.
    """

    SYSTEM_EXTRACTED = "system_extracted"
    SYSTEM_INTERPRETED = "system_interpreted"
    REQUIRES_HUMAN_DETERMINATION = "requires_human_determination"


class DecisionBoundaryElement(BaseModel):
    """One element in a decision draft with explicit origin marking."""

    content: str = Field(
        description="The text content of this element in the draft.",
    )
    origin: DecisionOrigin = Field(
        description=(
            "Whether this element was extracted from documents, interpreted "
            "by the system, or requires human determination."
        ),
    )
    source_document: str | None = Field(
        default=None,
        description=(
            "For SYSTEM_EXTRACTED: identifier or name of the source document. "
            "For SYSTEM_INTERPRETED: identifier of the norm or rule applied."
        ),
    )
    confidence_note: str | None = Field(
        default=None,
        description=(
            "For SYSTEM_INTERPRETED: the key assumption underlying this "
            "interpretation.  If this assumption does not hold, the "
            "interpretation may not apply."
        ),
    )


class DecisionBoundaryReport(BaseModel):
    """Transparency report for a system-generated decision draft.

    Provides an element-level breakdown of what the system extracted,
    what it interpreted, and what the Sachbearbeiter must determine.
    """

    project_id: str = Field(
        description="Project this decision draft belongs to.",
    )
    document_id: str = Field(
        description="Document (application) this decision addresses.",
    )
    elements: list[DecisionBoundaryElement] = Field(
        description="All elements of the decision draft with origin marking.",
    )
    system_extracted_count: int = Field(
        description="Number of elements directly extracted from source documents.",
    )
    system_interpreted_count: int = Field(
        description="Number of elements involving system interpretation.",
    )
    human_required_count: int = Field(
        description="Number of elements requiring human determination.",
    )

    @property
    def total_elements(self) -> int:
        """Total number of elements in the draft."""
        return len(self.elements)

    @property
    def human_required_ratio(self) -> float:
        """Fraction of elements requiring human determination."""
        if not self.elements:
            return 0.0
        return self.human_required_count / len(self.elements)
