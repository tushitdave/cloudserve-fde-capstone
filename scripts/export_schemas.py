"""Export versioned Pydantic handoff schemas for API and agent review."""

import json
from pathlib import Path

from cloudserve import contracts


NAMES = [
    "NormalizedTicket", "EventEnvelope", "ClassificationResult", "EvidenceBundle",
    "RoutingDecision", "DraftAnswer", "VerificationReport", "ValidationResult",
    "EscalationPacket", "FinalResult", "SourceRecord", "KnowledgeWorkItem",
    "CanonicalDocument", "KnowledgeChunk", "IndexManifest", "SourceLineage", "QuarantineRecord",
]


def export(directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in NAMES:
        path = directory / f"{name}.v1.schema.json"
        path.write_text(json.dumps(getattr(contracts, name).model_json_schema(), indent=2) + "\n")
        paths.append(path)
    return paths


if __name__ == "__main__":
    output = Path(__file__).resolve().parents[1] / "docs" / "schemas"
    print(f"Exported {len(export(output))} schemas to {output}")
