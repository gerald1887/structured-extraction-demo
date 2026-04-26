# structured-extraction-demo

Deterministic CLI-based LLM extraction system that converts text → strict JSON with schema validation, reproducible runs, and machine-readable artifacts.

---
## Requirements

- Python 3.11+
- OpenAI API key
---
## Setup

```
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```
---
## Before Running

```
mkdir -p outputs
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
## Sentinel artifact validation (optional)

Install Sentinel CLI in the same virtualenv. Validation in this repo is true black-box CLI invocation via subprocess (no `sentinel.*` Python imports). This does **not** run `sentinel run` and does **not** make a second LLM call.

Install (from a local clone of the Sentinel CLI repo, path may vary):

```
pip install -e /path/to/sentinel-cli
```

Two steps (run extraction, then validate the file on disk):

```
extract run \
  --input inputs/sample_1.txt \
  --schema schemas/extraction_schema.json \
  --output outputs/result.json

python3 scripts/validate_artifact_sentinel.py \
  --input outputs/result.json \
  --schema schemas/extraction_schema.json
```

Optional one-shot wrapper (single provider call; validation delegates to Sentinel CLI):

```
./scripts/extract_then_validate.sh run \
  --input inputs/sample_1.txt \
  --schema schemas/extraction_schema.json \
  --output outputs/result.json
```

`validate_artifact_sentinel.py` exit codes:
- `0` = success (`sentinel` exits `0`)
- `1` = contract failure (`sentinel` exits `1`)
- `2` = execution/setup/internal failure (missing files, invalid JSON artifact, missing/broken Sentinel CLI, or non-standard Sentinel exit code)

By default the validator calls:

```
sentinel validate --input <artifact> --schema <schema>
```

If your Sentinel CLI uses a different invocation shape, override it:

```
SENTINEL_BIN=/path/to/sentinel \
SENTINEL_VALIDATE_ARGS='validate --input {input} --schema {schema}' \
python3 scripts/validate_artifact_sentinel.py \
  --input outputs/result.json \
  --schema schemas/extraction_schema.json
```

The wrapper returns `extract`’s exit code on extraction failure, otherwise the validator’s exit code.

Standalone artifact validation command (no extraction/provider call):

```
python3 -m extractor.cli validate \
  --input outputs/result.json \
  --schema schemas/extraction_schema.json
```

Optional failure capture (written only when validation fails):

```
python3 -m extractor.cli validate \
  --input outputs/result.json \
  --schema schemas/extraction_schema.json \
  --failure-output outputs/validation_failure.json
```

Optional success capture (written only when validation succeeds):

```
python3 -m extractor.cli validate \
  --input outputs/result.json \
  --schema schemas/extraction_schema.json \
  --success-output outputs/validation_success.json
```

Validation capture artifact schema (`--success-output` and `--failure-output`):

```
{
  "status": "PASS" | "FAIL" | "ERROR",
  "exit_code": <integer>,
  "stdout": "<captured stdout>",
  "stderr": "<captured stderr>"
}
```

Replay a saved validation artifact (no provider/Sentinel call):

```
extract replay --input outputs/validation_success.json
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

Artifact equality diff:

```
extract diff-artifacts \
  --expected outputs/validation_success.json \
  --actual outputs/validation_failure.json
```

`diff-artifacts` validates both inputs as unified artifact objects before comparison.
If `--expected` is invalid, it fails first with structured error JSON (exit `2`);
`--actual` is validated only after `--expected` is valid.
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
---