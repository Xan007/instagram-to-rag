import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

class InterestFilter:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set. Cannot use Gemini filter.")
        self.client = genai.Client(api_key=api_key)
        
    def evaluate(self, description: str, hashtags: list, interests: str) -> str:
        """
        Evaluates if the post content matches the given interests.
        Returns 'YES', 'NO', or 'UNSURE'.
        """
        if not interests.strip():
            return "YES" # If no interests defined, accept everything
            
        content = f"Description: {description}\nHashtags: {', '.join(hashtags)}"
        
        prompt = f"""
You are an intelligent filter. The user is only interested in these topics: "{interests}".
Read the following Instagram post description and hashtags.
If the post is clearly about any of the user's interests, respond with exactly "YES".
If the post is clearly NOT about any of the interests, respond with exactly "NO".
If it is impossible to tell just from the text (e.g. it says "Watch this video to find out!" or has no text), respond with exactly "UNSURE".

Post Content:
{content}

Response (YES, NO, or UNSURE):"""
        
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model='gemini-3.5-flash-lite',
                    contents=prompt
                )
                result = response.text.strip().upper()
                if result in ["YES", "NO", "UNSURE"]:
                    return result
                if "YES" in result: return "YES"
                if "NO" in result: return "NO"
                return "UNSURE"
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    print(f"Gemini API rate limit reached. Waiting 15s before retry (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(15)
                else:
                    print(f"Error calling Gemini API for filtering: {e}")
                    return "UNSURE"
        return "UNSURE"
