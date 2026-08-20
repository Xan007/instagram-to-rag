import os
import time
import warnings
from typing import List, Dict
from google import genai
from dotenv import load_dotenv

warnings.filterwarnings("ignore")
load_dotenv()

FALLBACK_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.7-flash",
    "gemini-3.6-flash"
]

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
                print(f"Uploading {item['type']} {path} to Gemini...")
                gfile = self.client.files.upload(file=path)
                
                if item["type"] == "video":
                    while gfile.state.name == "PROCESSING":
                        print("Waiting for video processing...")
                        time.sleep(2)
                        gfile = self.client.files.get(name=gfile.name)
                        
                    if gfile.state.name == "FAILED":
                        print(f"Warning: processing failed for {path}")
                        continue
                        
                uploaded_files.append(gfile)
                
            prompt = f"""
You are an expert knowledge extractor for an AI knowledge base.
Review the provided media (images, slides, or video/audio) and the post's caption.

Original Caption:
"{post_description}"

Task:
Extract all dense, valuable factual knowledge, advice, recipes, exact ingredients/quantities, workout steps, or dietary rules presented across the visual content and audio.
Provide a clear, structured markdown summary. Do not include introductory/concluding greetings or fluff. Focus on actionable information and details.
"""
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
                            print(f"Model {model_name} is experiencing 503 high demand. Trying next model...")
                            break # Fallback to next model immediately
                        elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                            print(f"Rate limit on {model_name}. Waiting 10s...")
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
