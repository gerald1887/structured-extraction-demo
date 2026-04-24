# structured-extraction-demo

Minimal CLI-based LLM extraction app.

## Setup

1. Use Python 3.11+
2. Install dependencies:

```bash
pip install -e .
```

## Set API key

```bash
export OPENAI_API_KEY="your_api_key_here"
```

## Run CLI

```bash
extract run --input inputs/sample_1.txt --schema schemas/extraction_schema.json --output outputs/result.json
```

## Example

```bash
extract run --input inputs/sample_1.txt --schema schemas/extraction_schema.json --output outputs/sample_1_output.json --model gpt-4.1-mini
```

## Simulate provider failures

```bash
extract run --input inputs/sample_1.txt --schema schemas/extraction_schema.json --output outputs/result.json --simulate-provider-error timeout
extract snapshot --input inputs/sample_1.txt --schema schemas/extraction_schema.json --output outputs/golden.json --simulate-provider-error rate_limit
extract compare --input inputs/sample_1.txt --schema schemas/extraction_schema.json --snapshot outputs/golden.json --simulate-provider-error invalid_response
```

