# PII/GDPR Detection and Sanitization Pipeline

Multilingual (EN, HU, ES) PII detection and sanitization for knowledge-base ingestion.

**Definition of done:** See [docs/PII_GDPR_DEFINITION_OF_DONE.md](../../../docs/PII_GDPR_DEFINITION_OF_DONE.md) for the official supported entity list, implementation status (implemented / partially / planned), and success criteria. Layered detection: regex, NER (spaCy/Stanza), context hints, email classifier, vehicle and technical ID detectors; policy engine and configurable sanitizer.

## Install

From project root:

```bash
pip install pydantic langdetect
# Optional NER:
pip install spacy && python -m spacy download en_core_web_sm
pip install spacy && python -m spacy download es_core_news_sm
pip install stanza  # and run once: stanza.download("hu")
```

## Run tests

```bash
pytest tests/test_pii_gdpr_*.py -v
```

## Usage

```python
from apps.knowledge.pii_gdpr import IngestionPipeline, AnalyzerConfig, PolicyConfig

pipeline = IngestionPipeline(
    analyzer_config=AnalyzerConfig(mask_threshold=0.85),
    policy_config=PolicyConfig(mode="balanced", allow_role_based_emails=True),
)
result = pipeline.run("Raw text with email user@example.com and phone +36 30 123 4567.")
print(result["sanitized_text"])
print(result["summary"].total_detections)
```

## Architecture

- **detectors/**: Regex, NER (optional), context (sensitive hints), email classifier, vehicle, technical IDs.
- **policy/**: Maps entity types to risk and recommended action (strict/balanced/permissive).
- **sanitization/**: MASK (placeholder), GENERALIZE (e.g. "contact person"), KEEP.
- **pipeline/**: Language detection → run detectors → merge/dedupe → policy → sanitize → summary.
