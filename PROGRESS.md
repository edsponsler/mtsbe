# MTSBE Project State & Handoff

## Current Status
* **Current Phase:** We have successfully completed **Phases 1 through 5** of the initial Proof of Concept (PoC).
* **Accomplishments Across All Phases:**
  * **Phase 1 (Data Acquisition & Local ETL):**
    * Created `src/etl/osis_parser.py` parsing the Morphological Hebrew Bible OSIS XML into 1,583 chunks (50 chapter-level pericopes and 1,533 verses).
    * Implemented fallback logic for OSIS XMLs lacking `<div type="section">` tags.
    * Created `src/etl/sefaria_linker.py` mapping Sefaria Midrash graph links directly into the `"midrash"` arrays of parent pericope chunks.
  * **Phase 2 (Cloud Infrastructure & Database Initialization):**
    * Initialized GCP project (`mtsbe-1208613`), billing budgets, and Cloud SQL instance (`mtsbe-db`).
    * Created and applied `src/db/schema.sql` initializing `pgvector` alongside `pericopes` and `verses` relational tables.
  * **Phase 3 (Embedding & Ingestion):**
    * Built `src/etl/embedder.py` and `src/etl/ingest.py` to embed pericopes using Vertex AI (`gemini-embedding-2` at 768 dims in `us` region) and upsert into Cloud SQL with HNSW index.
  * **Phase 4 (Application Logic / API):**
    * Built FastAPI backend (`src/api/main.py`) executing two-stage Retrieval-Augmented Generation (RAG) using `gemini-3.8-flash` via Vertex AI.
  * **Phase 5 (Review, Refinement & Full-Stack UI):**
    * **Model & Embedding Tuning:** Transitioned generation to `gemini-3.8-flash` and embeddings to `gemini-embedding-2` under Vertex AI `us` multi-region for reduced latency and budget efficiency.
    * **Dual-Language Corpus Support (BSB & Hebrew):** Developed `src/ingest_bsb.py` to ingest the modern, open Berean Standard Bible (BSB), adding `english_text` columns across pericopes and verses while preserving original Hebrew.
    * **Shareable Narratives (GCS):** Integrated Google Cloud Storage (`mtsbe-narratives-1208613`) to persist synthesized narratives and added `/shared/{share_id}` endpoint.
    * **Interactive Next.js Frontend:** Scaffolded a scholarly Next.js client (`frontend/`) supporting live queries, synthesized narrative display, copy-to-clipboard sharing, and canonical source cards with expandable RTL Hebrew text.
    * **Local Development Automation:** Added `start_dev.sh` to orchestrate `cloud-sql-proxy`, `uvicorn`, and `next dev` concurrently.
    * **Repository Cleanup:** Cleaned up temporary test scripts and sample data files, and pinned dependencies in `requirements.txt`.

## Crucial Context & Budget Guidelines
* **Cost Constraint:** Strict $1,000 budget for GCP architectural iterations/PoC, and $1,000 reserved for operational use.
* **Billing Strategy (Vertex AI):** All Gemini SDK calls are routed through the **Vertex AI backend** (`vertexai=True` in `google-genai` client, region `us`) to consume GenAI App Builder and general GCP credits.
* **Granular Pericopes Technical Debt:** Genesis is currently chunked at the chapter level (50 pericopes). To achieve granular story-level pericope boundaries (e.g. "The Binding of Isaac"), future ETL will ingest an English OSIS XML with editorial section headings.

## Immediate Next Steps
1. **Corpus & Tradition Expansion ("Multi-Tradition" Core):**
   * Ingest remaining books of the Torah / Old Testament or New Testament.
   * Ingest extra-biblical traditions: Early Church Fathers (via CCEL) and Josephus (via Perseus) to realize multi-tradition cross-commentary.
2. **Granular Pericope Headings:**
   * Ingest an English OSIS XML with sub-chapter story headings (e.g., STEPBible or WEB) so pericopes represent specific stories rather than full chapters.
3. **Production Deployment:**
   * Containerize FastAPI backend and Next.js frontend for Cloud Run deployment with Cloud SQL connection integration.

