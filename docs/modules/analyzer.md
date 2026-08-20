# Analyzer Module (`src/analyzer/`)

## Responsibility
Transforms raw media files (videos, audio, carousel slides, infographics) and post captions into dense, structured, factual knowledge representations.

## Implementations

### `GeminiAnalyzer` (`src/analyzer/gemini_analyzer.py`)
- Leverages the official Google GenAI SDK (`google.genai`) with model **`gemini-3.6-flash`**.
- Handles multimodal inputs:
  - `.mp4` video files (watching visuals + transcribing spoken audio).
  - `.jpg` / `.png` carousel slides and infographics (OCR + visual interpretation).
- Waits for file state readiness using Gemini Files API.
- Extracts dense actionable knowledge: exact ingredient grams, nutritional facts (calories, macros), workout steps, or specific advice.
- **Ephemeral Storage Guarantee**: Files uploaded to Google Cloud are permanently deleted in a `finally:` block immediately after content generation.
