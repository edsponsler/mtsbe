# Proof of Concept (PoC) Implementation Plan: Genesis

Based on our architectural decisions, this document outlines the step-by-step implementation plan for the Multi-Tradition Semantic Bible Engine (MTSBE) Proof of Concept.

## Architectural Decisions Locked In
1. **Scope:** Single Book (Genesis) – to maximize iteration speed and minimize initial cost.
2. **Database:** Cloud SQL for PostgreSQL (with `pgvector`) – for unified relational graphing and vector search.
3. **ETL Strategy:** Local Python Scripts – for cost-free, rapid data parsing, generating JSON payloads that will be pushed to the DB.
4. **Source Material:** STEPBible (OSIS XML) + Sefaria (CC0) + CCEL – ensuring we have robust structural markup (pericopes/milestones).

---

## Phase 1: Data Acquisition & Local ETL (The "Zero-Cost" Foundation)
*Goal: Extract, transform, and map the raw texts into our 3-tier hierarchical schema without incurring cloud compute costs.*

1. **Acquire Source Texts:**
   - Download the Genesis OSIS XML from STEPBible (verifying their AI/derivative use policy).
   - Download the Sefaria Open-Data dumps for Genesis (specifically *Genesis Rabbah* and the `links.json` graph).
   - (Optional for PoC) Identify a public domain translation of Josephus' *Antiquities of the Jews* covering the Genesis period.
   
   > [!IMPORTANT]
   > **Observation on Source Text Structure:** To ensure the parser can identify granular pericopes (e.g., "The Binding of Isaac") rather than falling back to full chapter-level chunks, the selected OSIS XML source *must* include editorial section headings (`<div type="section">` or `<title type="section">`). Some scholarly sources (like MorphHB) omit these. We will need an English OSIS XML with section headings to fulfill our North Star goals. We will revisit this requirement later in planning.
2. **Develop the Parsing Engine (Local Python):**
   - Write an OSIS XML parser to extract Book -> Chapter -> Pericope -> Verse chunks.
   - Write a Sefaria linker to map `links.json` references to the corresponding Genesis pericope/verse IDs.
3. **Output Generation:**
   - Generate local JSON files structured exactly as defined in the `architecture.md` schema.

## Phase 2: Cloud Infrastructure & Database Initialization
*Goal: Stand up the cost-optimized GCP foundation.*

1. **Cost Monitoring Setup:**
   - Define a GCP Budget of $500 for the initial PoC iteration (reserving the remaining $500).
   - Set up billing alerts at 50%, 90%, and 100% of the threshold.
   - Apply resource labels (e.g., `env: poc`, `component: database`) for granular tracking.
2. **Cloud SQL Deployment:**
   - Provision a minimal Cloud SQL for PostgreSQL instance.
   - Enable the `pgvector` extension.
3. **Schema Definition & Data Load:**
   - Define tables for `verses`, `pericopes`, `commentaries` (Midrash), and a `cross_references` edge table.
   - Write a script to upload the Phase 1 JSON chunks into the database.

## Phase 3: Embedding Pipeline & Vector Search
*Goal: Make the biblical text and traditions semantically searchable.*

1. **Generate Embeddings:**
   - Use the Vertex AI Python SDK (calling `text-embedding-004`).
   - Iterate through the `verses` and `pericopes` in the database, requesting embeddings from Vertex AI.
   - *Cost Control:* Genesis is relatively small, so embedding costs will be negligible, but we will track API usage.
2. **Store and Index Vectors:**
   - Save the returned vectors into the `pgvector` columns in Cloud SQL.
   - Create HNSW (Hierarchical Navigable Small World) indexes in PostgreSQL for sub-second vector search.

## Phase 4: Augmented Generation Harness
*Goal: Bring the text to life using Gemini 3.8 (Pro vs Flash evaluation).*

1. **Retrieval API:**
   - Build a lightweight local Python/FastAPI harness.
   - Implement the Two-Stage Retrieval Flow:
     - Execute a vector similarity search in PostgreSQL against the user's query to find the relevant pericope.
     - Execute a graph traversal (SQL JOINs) to fetch all linked Midrash/Josephus commentary for that pericope.
2. **LLM Integration:**
   - Construct the "Persona & Context-Integrated Story Generation Prompt".
   - Feed the retrieved biblical text + commentaries into Gemini 3.8 via the Vertex AI SDK.
   - Stream the generated contextual narrative back to the user.

## Phase 5: Review & Refinement
*Goal: Analyze the results and refine before scaling.*

1. **Cost Analysis:** Review billing reports to identify the cost drivers (e.g., SQL instance uptime vs. API calls).
2. **Quality Audit:** Review the generated narratives for historical accuracy, dramatic immersion, and adherence to the original texts.
3. **Scale Planning:** Document required changes before transitioning the local ETL scripts to Cloud Run Jobs and expanding to the full Torah.
