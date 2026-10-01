# MTSBE Project State & Handoff

## Current Status
* **Current Phase:** We have successfully completed **Phase 1 (Data Acquisition & Local ETL)** and **Phase 2 (Cloud Infrastructure & Database Initialization)**.
* **Accomplishments:**
  * Created `osis_parser.py` which successfully parsed the 1.8MB Morphological Hebrew Bible OSIS XML into 1,583 chunks (50 chapter-level pericopes and 1,533 verses).
  * Implemented fallback logic for OSIS XMLs lacking `<div type="section">` tags (falling back to chapter-level chunks).
  * Created `sefaria_linker.py` which successfully mapped Sefaria Midrash graph links directly into the `"midrash"` arrays of the relevant parent pericope chunks.
  * Successfully initialized GCP Project, set up billing budgets manually, and provisioned a Cloud SQL instance (`mtsbe-db`).
  * Created and successfully executed the `schema.sql` to initialize `pgvector` and the `pericopes` and `verses` tables in the `mtsbe_data` database.
  * All code and architecture plans have been committed and pushed to GitHub.

## Crucial Context to Remember
* **Cost Constraint:** We have a strict $1,000 budget for GCP architectural iterations/PoC, and $1,000 reserved for operational use.
* **Granular Pericopes Technical Debt:** To achieve the "North Star" of highly granular narratives (e.g., specific stories like "The Binding of Isaac"), we must eventually ingest an **English OSIS XML** (like STEPBible or WEB) that includes editorial section headings. The current parser is proven to work for both sections and chapters.
* **Model Selection:** We will use a staged A/B approach. We will evaluate output quality using **Gemini 3.8 Pro** as the baseline, and then test **Gemini 3.8 Flash** to see if it maintains sufficient quality to maximize our operational budget.

## Immediate Next Steps (Upon Resuming)
We are ready to begin **Phase 3: Embedding Generation & Ingestion**.
1. **Embedding Script:** Write a Python script (`src/etl/embedder.py`) that uses the Gemini API (`text-embedding-004`) to generate vectors for our parsed JSON chunks.
2. **Database Ingestion:** Write an ingestion script (`src/etl/ingest.py`) to connect to the Cloud SQL database and `INSERT` the JSON data along with their embeddings.
3. **Execution:** Run the pipeline locally to push the processed data into our newly initialized cloud database.

*To resume, simply tell the agent to "read PROGRESS.md and continue".*
