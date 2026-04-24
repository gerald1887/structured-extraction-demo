# structured-extraction-demo

Deterministic CLI-based LLM extraction system that converts text → strict JSON with schema validation, reproducible runs, and machine-readable artifacts.

---

## Requirements

- Python 3.11+
- OpenAI API key

---

## Setup

```
pip install -e .
```

---

## Configure API Key

```
export OPENAI_API_KEY="your_api_key_here"
```

---

## Core Command

```
extract run \
  --input inputs/sample_1.txt \
  --schema schemas/extraction_schema.json \
  --output outputs/result.json
```

---

## Output Artifacts

On success:

- outputs/result.json → extracted JSON (canonical format)
- outputs/result.json.meta.json → metadata

On failure:

- outputs/result.json.error.json → structured failure artifact

---

## Exit Codes

- 0 → success  
- 1 → contract failure (JSON parse / schema validation)  
- 2 → execution error (file / provider / internal)  

---

## Determinism Guarantees

- Strict JSON-only output
- Canonical JSON formatting (sorted keys, indent=2, newline)
- No retries, no randomness in pipeline
- Identical input → identical output artifacts (post-LLM boundary)

---

## Prompt Reproducibility

Each run computes:

- prompt_hash = SHA256(resolved prompt)

Enforced via:

```
extract run ... --expected-prompt-hash <hash>
```

Mismatch → fails before provider call.

---

## Provider Failure Simulation

```
extract run ... --simulate-provider-error timeout
extract run ... --simulate-provider-error rate_limit
extract run ... --simulate-provider-error invalid_response
```

- No API key required
- Exit code = 2

---

## Snapshot + Replay

Create snapshot:

```
extract snapshot \
  --input inputs/sample_1.txt \
  --schema schemas/extraction_schema.json \
  --output outputs/golden.json
```

Compare with snapshot:

```
extract compare \
  --input inputs/sample_1.txt \
  --schema schemas/extraction_schema.json \
  --snapshot outputs/golden.json
```

---

## Raw Output Capture + Replay

Capture:

```
extract run ... --capture-output outputs/raw.txt
```

Replay (no provider call):

```
extract run ... --replay-output outputs/raw.txt
```

---

## Diff CLI (JSON vs JSON)

```
extract diff \
  --expected outputs/expected.json \
  --actual outputs/actual.json
```

Exit codes:
- 0 → PASS  
- 1 → DIFF  
- 2 → ERROR  

---

## Schema Compatibility Check

```
extract schema-check \
  --input outputs/result.json \
  --new-schema schemas/new_schema.json
```

---

## Redaction

```
extract run ... --redaction-config redaction/config.json
```

- Runs after validation
- Deterministic transformations
- Metadata includes redaction_applied

---

## Input Validation (Pre-LLM)

Fails early for:

- empty input
- >100KB input
- invalid UTF-8

No provider call made.

---

## Summary Report (CI / Sentinel)

```
extract run ... --report outputs/run_report.json
extract diff ... --report outputs/diff_report.json
extract snapshot ... --report outputs/snapshot_report.json
```

- Deterministic JSON summary
- No timestamps
- Machine-readable

---

## Batch Mode

```
extract run \
  --input-dir inputs/ \
  --schema schemas/extraction_schema.json \
  --output-dir outputs/
```

- Processes .txt, .md, .json
- Deterministic ordering
- Summary printed to stdout

---

## Testing

```
python3 -m unittest discover -s tests -p "test_*.py" -q
```

---

## Project Scope

- CLI-only
- Single provider (OpenAI)
- No retries / orchestration
- No database / UI / services
- Strict JSON contract enforcement

---

## Purpose

This project is designed as a real LLM system for:

- deterministic testing
- failure analysis
- regression detection
- external validation (e.g., Sentinel)
