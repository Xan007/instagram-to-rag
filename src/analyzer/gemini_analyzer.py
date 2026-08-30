import logging
import os
import time
import warnings
from typing import List, Dict
from google import genai
from config.env import load_runtime_env

warnings.filterwarnings("ignore")
load_runtime_env()

logger = logging.getLogger(__name__)

FALLBACK_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.7-flash",
    "gemini-3.6-flash"
]

EXTRACTION_PROMPT_TEMPLATE = """
You are an expert knowledge extractor building a permanent AI knowledge base from creator content.
Analyze the provided media (video with audio, images, or slides) together with the post's caption.

Original Caption:
"{post_description}"

Task:
Extract ALL dense, factual, actionable knowledge shown OR spoken in the media, plus anything valuable from the caption.

Hard rules:
1. Copy every number EXACTLY as stated: reps x sets (e.g. 12x3), seconds, grams, ml, calories, temps, times. Never round, convert, or invent numbers.
2. Transcribe the key points of the SPOKEN audio (steps, tips, warnings, corrections) - not filler.
3. Read and include relevant ON-SCREEN text: overlays, lists, whiteboards, ingredient labels, exercise names.
4. Write the output in the SAME language as the original caption.
5. If the media adds nothing beyond the caption, say so explicitly on a "Notes:" line and extract only from the caption.
6. No greetings, no conclusions, no fluff, no opinions of your own. Facts and instructions only.

Output format (markdown, use these exact section headers; omit a section only if truly empty):

## Topic
(one line: what this post teaches)

## Steps / Method
(numbered steps or exercise list with exact sets/reps/durations/quantities)

## Key Numbers
(bullet list of every measurement, amount, dosage or timing mentioned)

## On-Screen Text
(text visible in frames/slides that is not already covered above)

## Spoken Key Points
(the most important things said in the audio)

## Notes
(equipment needed, common mistakes warned about, who it's for, or 'media adds nothing beyond caption')
"""


def build_extraction_prompt(post_description: str) -> str:
    """Assemble the multimodal extraction prompt. Pure function."""
    return EXTRACTION_PROMPT_TEMPLATE.format(post_description=post_description.strip())

class GeminiAnalyzer:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        self.client = genai.Client(api_key=api_key)
        
    def extract_knowledge(self, media_files: List[Dict[str, str]], post_description: str) -> str:
        """
        Uploads media files to Gemini and extracts structured knowledge.
        Automatically falls back across multiple Gemini models if 503 UNAVAILABLE or 429 occurs.
        """
        uploaded_files = []
        try:
            for item in media_files:
                path = item["path"]
                logger.info("Uploading %s %s to Gemini...", item["type"], path)
                gfile = self.client.files.upload(file=path)
                
                if item["type"] == "video":
                    while gfile.state.name == "PROCESSING":
                        logger.info("Waiting for video processing...")
                        time.sleep(2)
                        gfile = self.client.files.get(name=gfile.name)
                        
                    if gfile.state.name == "FAILED":
                        logger.warning("Processing failed for %s", path)
                        continue
                        
                uploaded_files.append(gfile)
                
            prompt = build_extraction_prompt(post_description)
            contents = uploaded_files + [prompt] if uploaded_files else [prompt]
            
            last_error = None
            for model_name in FALLBACK_MODELS:
                for attempt in range(2):
                    try:
                        chat = self.client.chats.create(model=model_name)
                        response = chat.send_message(contents)
                        return response.text.strip()
                    except Exception as e:
                        last_error = e
                        err_str = str(e)
                        if "503" in err_str or "UNAVAILABLE" in err_str:
                            logger.info("Model %s is experiencing 503 high demand. Trying next model...", model_name)
                            break
                        elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                            logger.info("Rate limit on %s. Waiting 10s...", model_name)
                            time.sleep(10)
                        else:
                            break
                            
            raise RuntimeError(f"All fallback models failed for knowledge extraction: {last_error}")
            
        finally:
            for gfile in uploaded_files:
                try:
                    self.client.files.delete(name=gfile.name)
                except Exception:
                    pass
