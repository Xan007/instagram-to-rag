from apify_client import ApifyClient
import os
from dotenv import load_dotenv

load_dotenv()
client = ApifyClient(os.getenv("APIFY_API_KEY"))

run_input = {
    "directUrls": ["https://www.instagram.com/bejaranofit/"],
    "resultsType": "posts",
    "resultsLimit": 1
}

run = client.actor("apify/instagram-scraper").call(run_input=run_input)
for item in client.dataset(run["defaultDatasetId"]).iterate_items():
    print(item.keys())
    break
