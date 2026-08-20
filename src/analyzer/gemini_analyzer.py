import os
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

class GeminiAnalyzer:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        self.client = genai.Client(api_key=api_key)
        
    def extract_knowledge(self, video_path: str, post_description: str) -> str:
        """
        Uploads video to Gemini, extracts knowledge (audio transcription + visual context).
        """
        print(f"Uploading video {video_path} to Gemini...")
        video_file = self.client.files.upload(file=video_path)
        
        # Wait for processing if needed
        while video_file.state.name == "PROCESSING":
            print("Waiting for video processing...")
            time.sleep(2)
            video_file = self.client.files.get(name=video_file.name)
            
        if video_file.state.name == "FAILED":
            raise ValueError(f"Video processing failed for {video_path}")
            
        prompt = f"""
You are an expert knowledge extractor. Watch and listen to this Instagram Reel.
The post's original description is: "{post_description}".
Extract all valuable knowledge, tips, recipes, facts, or instructions mentioned in the video (both spoken and visually presented).
Write a comprehensive but concise summary of the knowledge. 
Focus entirely on the actual information provided, ignoring filler content.
"""
        try:
            response = self.client.models.generate_content(
                model='gemini-3.6-flash',
                contents=[video_file, prompt]
            )
            result = response.text
        finally:
            # Always clean up the file from Gemini's servers
            self.client.files.delete(name=video_file.name)
            
        return result
