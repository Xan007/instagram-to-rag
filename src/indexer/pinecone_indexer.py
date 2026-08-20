import json
from pathlib import Path
from typing import Dict, Any

class PineconeIndexer:
    def __init__(self, output_dir: str = "data/processed"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # In the future, initialize Pinecone client here
        
    def index_post(self, username: str, metadata: Dict[str, Any], extracted_text: str):
        """
        Placeholder for vector database indexing.
        For now, saves the processed knowledge locally to prove the pipeline works.
        """
        document = {
            "id": metadata["id"],
            "url": metadata["url"],
            "username": username,
            "original_description": metadata["description"],
            "extracted_knowledge": extracted_text
        }
        
        # Save to local JSON as a mock for Pinecone
        file_path = self.output_dir / f"{metadata['id']}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(document, f, indent=4, ensure_ascii=False)
            
        print(f"-> [Mock Indexer] Saved extracted knowledge for {metadata['id']} to {file_path}")
