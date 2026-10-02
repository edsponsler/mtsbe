import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
from pgvector.psycopg2 import register_vector
from google import genai
from google.genai import types

# Initialize FastAPI app
app = FastAPI(title="MTSBE Multi-Tradition Semantic Bible Engine API")

# Initialize Gemini Client with Vertex AI backend
try:
    ai_client = genai.Client(
        vertexai=True,
        project="mtsbe-1208613",
        location="us-central1"
    )
except Exception as e:
    print(f"Warning: Failed to initialize Vertex AI client. Make sure ADC is configured. {e}")
    ai_client = None

# Database connection details
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "mtsbe_data")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "ChangeThisStrongPassword123!")

def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    register_vector(conn)
    return conn

# Request/Response Models
class QueryRequest(BaseModel):
    query: str
    num_results: int = 3

class SourceContext(BaseModel):
    id: str
    title: str
    text: str
    midrash_links: list

class NarrativeResponse(BaseModel):
    narrative: str
    sources: list[SourceContext]

@app.post("/generate", response_model=NarrativeResponse)
def generate_narrative(request: QueryRequest):
    if not ai_client:
        raise HTTPException(status_code=500, detail="Vertex AI client not initialized. Check ADC credentials.")

    try:
        # Step 1: Embed the user query
        embed_response = ai_client.models.embed_content(
            model="gemini-embedding-2",
            contents=request.query,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=768
            )
        )
        query_embedding = embed_response.embeddings[0].values

        # Step 2: Retrieve relevant pericopes using pgvector
        conn = get_db_connection()
        cur = conn.cursor()
        
        # We use <-> for L2 distance (or <=> for cosine distance). HNSW index uses vector_l2_ops by default.
        cur.execute("""
            SELECT id, pericope_title, text, external_links, embedding <-> %s::vector AS distance
            FROM pericopes
            ORDER BY distance LIMIT %s
        """, (query_embedding, request.num_results))
        
        results = cur.fetchall()
        cur.close()
        conn.close()

        if not results:
            raise HTTPException(status_code=404, detail="No relevant context found.")

        # Step 3: Format the context for the LLM
        sources = []
        context_str = "--- BIBLICAL CONTEXT ---\n"
        for row in results:
            p_id, title, text, links, dist = row
            midrash = links.get('midrash', []) if isinstance(links, dict) else []
            
            sources.append(SourceContext(
                id=p_id,
                title=title or "Unknown Pericope",
                text=text,
                midrash_links=midrash
            ))
            
            context_str += f"\nPericope: {title}\nText: {text}\n"
            if midrash:
                context_str += f"Associated Midrash references: {', '.join(midrash)}\n"
        
        # Step 4: Generate the narrative using Gemini
        system_instruction = """
You are an expert biblical historian, exegete, and narrative writer.
Synthesize the provided biblical narrative with its ancient interpretive and cultural layers:

1. Biblical Anchor: Ground the core action strictly in the retrieved pericope text.
2. Jewish Midrashic Layer (OT): Introduce rabbinic motifs, psychological subtext, 
   and dialogues recorded in Midrash Rabbah or Tanchuma (e.g., Satan's testing, Sarah's perspective).
3. Patristic Typology (NT): Weave in the theological and symbolic lens of the Early 
   Church Fathers where relevant (e.g., sacrificial imagery, prophetic fulfillment).
4. Material & Political Reality (Josephus): Ground the setting, sensory details, 
   military realities, topography, and political tensions using the historical records of Flavius Josephus.

Maintain a clear distinction between the primary biblical narrative and secondary 
historical/legendary traditions without breaking dramatic immersion.
"""
        
        prompt = f"{context_str}\n\nUser Request: {request.query}\n\nGenerate the contextual narrative:"
        
        generation = ai_client.models.generate_content(
            model="gemini-3.8-pro",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7
            )
        )

        return NarrativeResponse(
            narrative=generation.text,
            sources=sources
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "MTSBE API"}
