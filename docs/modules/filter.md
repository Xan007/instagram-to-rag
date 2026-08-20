# Filter Module (`src/filter/`)

## Responsibility
Acts as an intelligent, zero-cost gatekeeper. Evaluates whether an Instagram post's title, description, and hashtags align with the specific user interests configured for that creator before downloading heavy media.

## Implementation (`src/filter/interest_filter.py`)
- Powered by **`gemini-3.5-flash-lite`** for high throughput, sub-second latency, and minimal token consumption.
- Evaluates raw captions and hashtags against the comma-separated interest list.
- Returns a 3-way classification:
  - **`YES`**: Post matches user interests -> proceed to download and deep analysis.
  - **`NO`**: Post is unrelated -> skipped immediately without downloading.
  - **`UNSURE`**: Caption is ambiguous or short -> kept for multimodal verification.
- Includes automatic exponential backoff retry for Google API rate limits (`429 RESOURCE_EXHAUSTED`).
