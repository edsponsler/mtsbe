import json
import os
import time
from typing import List, Dict, Any
from google import genai
from google.genai import types

# Use gemini-embedding-2 model as it is the current standard embedding model
MODEL_NAME = "gemini-embedding-2"

def load_data(file_path: str) -> List[Dict[str, Any]]:
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data: List[Dict[str, Any]], file_path: str):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generate_embeddings(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Initialize genai client using Vertex AI backend to consume GCP credits
    # This automatically uses Google Cloud Application Default Credentials (ADC)
    client = genai.Client(
        vertexai=True,
        project="mtsbe-1208613",
        location="us-central1"
    )

    embedded_data = []
    
    total = len(data)
    for i, item in enumerate(data):
        text = item.get("text", "")
        if i % 50 == 0:
            print(f"Embedding item {i+1}/{total}...")
            
        try:
            response = client.models.embed_content(
                model=MODEL_NAME,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=768
                )
            )
            
            new_item = item.copy()
            new_item["embedding"] = response.embeddings[0].values
            embedded_data.append(new_item)
            
        except Exception as e:
            print(f"Error generating embedding for item {i}: {e}")
            print("Retrying after 5 seconds...")
            time.sleep(5)
            response = client.models.embed_content(
                model=MODEL_NAME,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=768
                )
            )
            new_item = item.copy()
            new_item["embedding"] = response.embeddings[0].values
            embedded_data.append(new_item)
            
        # Small sleep to respect rate limits
        time.sleep(0.1)
        
    return embedded_data

def main():
    # Workspace root is likely current directory when running
    input_file = "data/processed/genesis_linked.json"
    output_file = "data/processed/genesis_embedded.json"
    
    if not os.path.exists(input_file):
        print(f"Input file not found: {input_file}")
        # Try relative to script dir just in case
        script_dir = os.path.dirname(os.path.abspath(__file__))
        input_file = os.path.join(script_dir, "../../data/processed/genesis_linked.json")
        output_file = os.path.join(script_dir, "../../data/processed/genesis_embedded.json")
        if not os.path.exists(input_file):
            return
        
    print(f"Loading data from {input_file}...")
    data = load_data(input_file)
    print(f"Loaded {len(data)} items.")
    
    print("Generating embeddings...")
    try:
        embedded_data = generate_embeddings(data)
    except ValueError as e:
        print(f"Setup Error: {e}")
        return
    except Exception as e:
        print(f"API Error: {e}")
        return
    
    print(f"Saving embedded data to {output_file}...")
    save_data(embedded_data, output_file)
    print("Done!")

if __name__ == "__main__":
    main()
