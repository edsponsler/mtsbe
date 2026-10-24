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
    * **Model & Embedding Tuning:** Integrated **Gemini 4 Argon** (`gemini-4-argon`) via Vertex AI `us` multi-region for superior creative writing, complex theological reasoning, and multi-perspective narrative synthesis, paired with `gemini-embedding-2` for dense retrieval. Added model selection metadata to both API and UI.
    * **Dual-Language Corpus Support (BSB & Hebrew):** Developed `src/ingest_bsb.py` to ingest the modern, open Berean Standard Bible (BSB), adding `english_text` columns across pericopes and verses while preserving original Hebrew.
    * **Shareable Narratives (GCS):** Integrated Google Cloud Storage (`mtsbe-narratives-1208613`) to persist synthesized narratives and added `/shared/{share_id}` endpoint.
    * **Interactive Next.js Frontend:** Scaffolded a scholarly Next.js client (`frontend/`) supporting live queries, synthesized narrative display, copy-to-clipboard sharing, model provenance badges, and canonical source cards with expandable RTL Hebrew text.
    * **Local Development Automation:** Added `start_dev.sh` to orchestrate `cloud-sql-proxy`, `uvicorn`, and `next dev` concurrently.
    * **Granular Pericope Segmentation:** Created `src/etl/ingest_granular_pericopes.py` to parse official Berean Standard Bible section headings (`bsb_tables.tsv`). Expanded Genesis from 50 coarse chapter chunks into 148 granular narrative pericopes (e.g., separating Gen 18 into *The Three Visitors*, *Sarah Laughs at the Promise*, and *Abraham Intercedes for Sodom*). Generated 768-dim embeddings for all 148 pericopes using `gemini-embedding-2` via Vertex AI and updated relational foreign key alignments across all 1,533 verses.
    * **Streaming Responses (Priority A):** Implemented Server-Sent Events (SSE) streaming endpoint `POST /generate/stream` in `src/api/main.py` using `ai_client.models.generate_content_stream` powered by `gemini-4-argon`. The frontend client (`frontend/src/app/page.tsx`) immediately renders canonical source cards and metadata upon vector retrieval (<1s), progressively displays streamed text chunks with a dynamic golden cursor and live badge, and persists completed narratives to Google Cloud Storage (`mtsbe-narratives-1208613`) for shareable links upon completion.
    * **Perspective Controls (Priority B):** Implemented user-steerable tradition controls allowing granular enabling/disabling of individual interpretive traditions (Rabbinic Midrash, Patristic Typology, and Historical Josephus) and narrative tone selection (Dramatic Story, Scholarly Exegesis, Contemplative). Added `PerspectiveConfig` and dynamic prompt compilation in `src/api/main.py`. Built a glassmorphism toolbar in `frontend/src/app/page.tsx` with active indicator pills and provenance tags across both the live client and shared narrative permalinks (`frontend/src/app/share/[id]/page.tsx`).
    * **Corpus Expansion & Grounded Commentaries (Priority C):** Extended PostgreSQL schema (`src/db/schema.sql`) with a dedicated `commentaries` table featuring 768-dim `pgvector` embeddings and an HNSW distance index (`tradition`, `author`, `work`, `reference`, `title`, `text`, `original_language_text`, `linked_pericope_ids`). Built `src/etl/ingest_commentaries.py` extracting, chunking, and embedding 120 rich commentary chunks: Flavius Josephus (*Antiquities of the Jews*, Book 1, 44 chunks), Jewish Midrash (*Genesis Rabbah* dual Hebrew + English via Sefaria API, 64 chunks), and Patristics (St. Augustine of Hippo, *The City of God* Books 15 & 16, 12 chunks). Upgraded FastAPI backend (`src/api/main.py`) to perform dual-vector search, filtering commentaries dynamically by active perspective toggles and injecting grounded commentary texts directly into Gemini 4 Argon's prompt context. Enhanced Next.js frontend with dedicated color-coded Commentary cards (`📜 Midrash` gold, `✝️ Patristic` indigo, `🏛️ Historical` emerald) with original language accordions across both live generator and shared view.

## Crucial Context & Budget Guidelines
* **Cost Constraint:** Strict $1,000 budget for GCP architectural iterations/PoC, and $1,000 reserved for operational use.
* **Billing Strategy (Vertex AI):** All Gemini SDK calls are routed through the **Vertex AI backend** (`vertexai=True` in `google-genai` client, region `us`) to consume GenAI App Builder and general GCP credits.
* **Granular Pericopes Resolution:** Genesis now has full sub-chapter narrative boundaries (148 pericopes). Future biblical book additions can follow this same BSB translation tables pipeline.
* **Database Volume:** Cloud SQL database contains 148 granular pericopes, 1,533 individual verses, and 120 embedded commentary chunks with HNSW vector indices.

## Immediate Next Steps
1. **Torah / Canonical Expansion (Priority D):**
   * Ingest remaining books of the Torah (Exodus, Leviticus, Numbers, Deuteronomy) using the BSB granular headings pipeline.
   * Expand commentary corpus across the new narrative arcs (e.g., Philo of Alexandria, Rashi, Origen, John Chrysostom).
2. **Production Cloud Run Deployment (Priority E):**
   * Containerize FastAPI backend and Next.js frontend for Cloud Run deployment with Cloud SQL connection integration.


