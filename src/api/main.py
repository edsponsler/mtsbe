import os
import json
import uuid
from google.cloud import storage
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import psycopg2
from pgvector.psycopg2 import register_vector
from google import genai
from google.genai import types

from fastapi.middleware.cors import CORSMiddleware

# Initialize FastAPI app
app = FastAPI(title="MTSBE Multi-Tradition Semantic Bible Engine API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini Client with Vertex AI backend
try:
    ai_client = genai.Client(
        vertexai=True,
        project="mtsbe-1208613",
        location="us"
    )
except Exception as e:
    print(f"Warning: Failed to initialize Vertex AI client. Make sure ADC is configured. {e}")
    ai_client = None

try:
    storage_client = storage.Client(project="mtsbe-1208613")
    bucket = storage_client.bucket("mtsbe-narratives-1208613")
except Exception as e:
    print(f"Warning: Failed to initialize GCS client: {e}")
    storage_client = None
    bucket = None

# Database connection details
INSTANCE_CONNECTION_NAME = os.environ.get("INSTANCE_CONNECTION_NAME")
DB_HOST = os.environ.get("DB_HOST", f"/cloudsql/{INSTANCE_CONNECTION_NAME}" if INSTANCE_CONNECTION_NAME else "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "mtsbe_data")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "ChangeThisStrongPassword123!")

def get_db_connection():
    conn_params = {
        "dbname": DB_NAME,
        "user": DB_USER,
        "password": DB_PASSWORD,
        "host": DB_HOST
    }
    if not DB_HOST.startswith("/"):
        conn_params["port"] = DB_PORT
    conn = psycopg2.connect(**conn_params)
    register_vector(conn)
    return conn

@app.get("/")
def root():
    return {
        "status": "healthy",
        "service": "mtsbe-api",
        "model": os.environ.get("NARRATIVE_MODEL", "gemini-4-argon"),
        "version": "1.0.0"
    }

@app.get("/health")
def health():
    return {"status": "ok"}

# Request/Response Models
class PerspectiveConfig(BaseModel):
    include_midrash: bool = True
    include_patristic: bool = True
    include_historical: bool = True
    narrative_tone: str = "dramatic"  # "dramatic", "scholarly", "meditative"

class QueryRequest(BaseModel):
    query: str
    num_results: int = 3
    model: str | None = None
    perspectives: PerspectiveConfig = PerspectiveConfig()

class SourceContext(BaseModel):
    id: str
    title: str
    text: str # We'll keep this as the English text
    hebrew_text: str
    midrash_links: list

class CommentaryContext(BaseModel):
    id: str
    tradition: str
    author: str
    work: str
    reference: str
    title: str
    text: str
    original_language_text: str | None = None

class NarrativeResponse(BaseModel):
    share_id: str | None = None
    model_used: str | None = None
    perspectives: PerspectiveConfig | None = None
    narrative: str
    sources: list[SourceContext]
    commentaries: list[CommentaryContext] = []

def build_system_instruction(perspectives: PerspectiveConfig) -> str:
    layers = ["1. Biblical Anchor: Ground the core action strictly in the retrieved pericope text."]
    layer_num = 2

    if perspectives.include_midrash:
        layers.append(
            f"{layer_num}. Jewish Midrashic Layer (OT): Introduce rabbinic motifs, psychological subtext, "
            "and dialogues recorded in Midrash Rabbah, Tanchuma, and the Talmud (e.g., Satan's testing, Sarah's perspective, aggadic debates)."
        )
        layer_num += 1
    else:
        layers.append(
            f"{layer_num}. Omit Rabbinic Midrash: Do not include rabbinic aggadah, midrashic debates, or post-biblical Jewish legends."
        )
        layer_num += 1

    if perspectives.include_patristic:
        layers.append(
            f"{layer_num}. Patristic Typology (NT): Weave in the theological and symbolic lens of the Early "
            "Church Fathers where relevant (e.g., sacrificial imagery, prophetic fulfillment, sacramental typology)."
        )
        layer_num += 1
    else:
        layers.append(
            f"{layer_num}. Omit Patristic Typology: Do not introduce Christian allegorical readings, patristic typologies, or New Testament fulfillment motifs."
        )
        layer_num += 1

    if perspectives.include_historical:
        layers.append(
            f"{layer_num}. Material & Political Reality (Josephus): Ground the setting, sensory details, "
            "military realities, topography, and political tensions using the historical records of Flavius Josephus and ancient Near Eastern antiquity."
        )
        layer_num += 1
    else:
        layers.append(
            f"{layer_num}. Omit Historical Speculation: Do not weave in external Greco-Roman or Josephus historiographical additions."
        )
        layer_num += 1

    if perspectives.narrative_tone == "scholarly":
        tone_instruction = (
            "Voice and Format: Present the synthesis in a rigorous, scholarly commentary style. "
            "Examine how each tradition interprets the pericope, comparing differences, theological nuances, and historical context."
        )
    elif perspectives.narrative_tone == "meditative":
        tone_instruction = (
            "Voice and Format: Present the synthesis in a contemplative, reflective devotional tone. "
            "Focus on the inner spiritual journey, existential weight, and ethical lessons of the text and traditions."
        )
    else:  # dramatic
        tone_instruction = (
            "Voice and Format: Present the synthesis as an evocative, immersive literary drama. "
            "Maintain dramatic tension, vivid sensory imagery, and psychological depth while maintaining clear distinctions between biblical anchor and interpretive traditions."
        )

    layers_text = "\n".join(layers)

    return f"""You are an expert biblical historian, exegete, and narrative writer.
Synthesize the provided biblical narrative with its ancient interpretive and cultural layers according to the following guidelines:

{layers_text}

{tone_instruction}
"""

def retrieve_context(query: str, num_results: int = 3, perspectives: PerspectiveConfig = PerspectiveConfig()):
    if not ai_client:
        raise HTTPException(status_code=500, detail="Vertex AI client not initialized. Check ADC credentials.")

    # Step 1: Embed the user query
    embed_response = ai_client.models.embed_content(
        model="gemini-embedding-2",
        contents=query,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=768
        )
    )
    query_embedding = embed_response.embeddings[0].values

    # Step 2: Retrieve relevant biblical pericopes using pgvector
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, pericope_title, english_text, text as hebrew_text, external_links, embedding <-> %s::vector AS distance
        FROM pericopes
        ORDER BY distance LIMIT %s
    """, (query_embedding, num_results))
    
    pericope_results = cur.fetchall()

    if not pericope_results:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="No relevant biblical context found.")

    sources = []
    context_str = "--- BIBLICAL CONTEXT ---\n"
    for row in pericope_results:
        p_id, title, english_text, hebrew_text, links, dist = row
        midrash = links.get('midrash', []) if isinstance(links, dict) else []
        display_text = english_text if english_text else hebrew_text

        sources.append(SourceContext(
            id=p_id,
            title=title or "Unknown Pericope",
            text=display_text,
            hebrew_text=hebrew_text,
            midrash_links=midrash
        ))
        
        context_str += f"\nPericope: {title}\nText: {display_text}\n"

    # Step 3: Retrieve grounded ancient commentaries & historical sources based on active perspective filters
    active_traditions = []
    if perspectives.include_midrash:
        active_traditions.append('midrash')
    if perspectives.include_patristic:
        active_traditions.append('patristic')
    if perspectives.include_historical:
        active_traditions.append('historical')

    commentaries = []
    if active_traditions:
        cur.execute("""
            SELECT id, tradition, author, work, reference, title, text, original_language_text, embedding <-> %s::vector AS distance
            FROM commentaries
            WHERE tradition = ANY(%s)
            ORDER BY distance LIMIT %s
        """, (query_embedding, active_traditions, 4))
        comm_results = cur.fetchall()

        if comm_results:
            context_str += "\n--- GROUNDED ANCIENT COMMENTARIES & HISTORICAL TRADITIONS ---\n"
            for row in comm_results:
                cid, trad, author, work, ref, ctitle, ctext, orig_lang, dist = row
                commentaries.append(CommentaryContext(
                    id=cid,
                    tradition=trad,
                    author=author or "",
                    work=work or "",
                    reference=ref or "",
                    title=ctitle or "",
                    text=ctext,
                    original_language_text=orig_lang
                ))
                context_str += f"\n[TRADITION: {trad.upper()} | SOURCE: {author} - {ref}]\nTitle: {ctitle}\nText: {ctext[:1500]}\n"

    cur.close()
    conn.close()

    return sources, commentaries, context_str

@app.post("/generate", response_model=NarrativeResponse)
def generate_narrative(request: QueryRequest):
    try:
        sources, commentaries, context_str = retrieve_context(request.query, request.num_results, request.perspectives)
        prompt = f"{context_str}\n\nUser Request: {request.query}\n\nGenerate the contextual narrative:"
        target_model = request.model or os.environ.get("NARRATIVE_MODEL", "gemini-4-argon")
        system_instruction = build_system_instruction(request.perspectives)

        generation = ai_client.models.generate_content(
            model=target_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7
            )
        )

        response_data = NarrativeResponse(
            share_id=str(uuid.uuid4()),
            model_used=target_model,
            perspectives=request.perspectives,
            narrative=generation.text,
            sources=sources,
            commentaries=commentaries
        )

        if bucket:
            try:
                blob = bucket.blob(f"{response_data.share_id}.json")
                blob.upload_from_string(response_data.model_dump_json(), content_type="application/json")
            except Exception as e:
                print(f"Failed to upload to GCS: {e}")

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate/stream")
def generate_narrative_stream(request: QueryRequest):
    try:
        sources, commentaries, context_str = retrieve_context(request.query, request.num_results, request.perspectives)
        prompt = f"{context_str}\n\nUser Request: {request.query}\n\nGenerate the contextual narrative:"
        target_model = request.model or os.environ.get("NARRATIVE_MODEL", "gemini-4-argon")
        share_id = str(uuid.uuid4())
        system_instruction = build_system_instruction(request.perspectives)

        def event_stream():
            # Emit immediate metadata event with canonical sources AND grounded commentary cards
            init_payload = {
                "type": "metadata",
                "share_id": share_id,
                "model_used": target_model,
                "perspectives": request.perspectives.model_dump(),
                "sources": [s.model_dump() for s in sources],
                "commentaries": [c.model_dump() for c in commentaries]
            }
            yield f"data: {json.dumps(init_payload)}\n\n"

            full_narrative = []
            try:
                stream = ai_client.models.generate_content_stream(
                    model=target_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.7
                    )
                )
                for chunk in stream:
                    if chunk.text:
                        full_narrative.append(chunk.text)
                        chunk_payload = {
                            "type": "chunk",
                            "text": chunk.text
                        }
                        yield f"data: {json.dumps(chunk_payload)}\n\n"

                completed_text = "".join(full_narrative)

                # Persist completed narrative to GCS for shareable permalinks
                if bucket:
                    try:
                        narrative_obj = NarrativeResponse(
                            share_id=share_id,
                            model_used=target_model,
                            perspectives=request.perspectives,
                            narrative=completed_text,
                            sources=sources,
                            commentaries=commentaries
                        )
                        blob = bucket.blob(f"{share_id}.json")
                        blob.upload_from_string(narrative_obj.model_dump_json(), content_type="application/json")
                    except Exception as e:
                        print(f"Failed to upload streaming narrative to GCS: {e}")

                yield f"data: {json.dumps({'type': 'done'})}\n\n"

            except Exception as e:
                err_payload = {"type": "error", "detail": str(e)}
                yield f"data: {json.dumps(err_payload)}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "MTSBE API"}

@app.get("/shared/{share_id}", response_model=NarrativeResponse)
def get_shared_narrative(share_id: str):
    if not bucket:
        raise HTTPException(status_code=500, detail="GCS storage not initialized")
        
    try:
        blob = bucket.blob(f"{share_id}.json")
        if not blob.exists():
            raise HTTPException(status_code=404, detail="Shared narrative not found")
            
        content = blob.download_as_string()
        data = json.loads(content)
        return NarrativeResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
