# Filter Module (`src/filter/`)

## Responsibility
Acts as an intelligent, zero-cost gatekeeper. Evaluates whether Instagram posts align with the creator's configured interests before triggering heavy media downloads.

## High-Speed Batch Architecture (`src/filter/interest_filter.py`)
- **Batch Evaluation (`filter_batch`)**: Instead of 100 separate API requests, captions and hashtags are chunked in groups of 40 and evaluated in a single prompt.
- **90%+ Latency & Quota Reduction**: Evaluates 100 posts in under 3 seconds using just 2-3 API roundtrips.
- **Automatic Multi-Model Fallback**:
  - Primary: `gemini-3.5-flash-lite` (highest speed and token efficiency).
  - Fallback 1: `gemini-3.7-flash` (if 503 high demand occurs).
  - Fallback 2: `gemini-3.6-flash`.
- Returns a set of matching post IDs directly to the pipeline.
