# MTSBE Project State & Handoff

## Current Status
* **Current Phase:** We have successfully completed **Phase 1 (Data Acquisition & Local ETL)**.
* **Accomplishments:**
  * Created `osis_parser.py` which successfully parsed the 1.8MB Morphological Hebrew Bible OSIS XML into 1,583 chunks (50 chapter-level pericopes and 1,533 verses).
  * Implemented fallback logic for OSIS XMLs lacking `<div type="section">` tags (falling back to chapter-level chunks).
  * Created `sefaria_linker.py` which successfully mapped Sefaria Midrash graph links directly into the `"midrash"` arrays of the relevant parent pericope chunks.
  * All code and architecture plans have been committed and pushed to GitHub.

## Crucial Context to Remember
* **Cost Constraint:** We have a strict $1,000 budget for GCP architectural iterations/PoC, and $1,000 reserved for operational use.
* **Granular Pericopes Technical Debt:** To achieve the "North Star" of highly granular narratives (e.g., specific stories like "The Binding of Isaac"), we must eventually ingest an **English OSIS XML** (like STEPBible or WEB) that includes editorial section headings. The current parser is proven to work for both sections and chapters.
* **Model Selection:** We will use a staged A/B approach. We will evaluate output quality using **Gemini 3.8 Pro** as the baseline, and then test **Gemini 3.8 Flash** to see if it maintains sufficient quality to maximize our operational budget.

## Immediate Next Steps (Upon Resuming)
We are beginning **Phase 2: Cloud Infrastructure & Database Initialization**.
1. **Initialize GCP Project:** Determine if we are using an existing project or creating a new one via `gcloud`.
2. **Setup Cost Monitoring:** Define the $500 threshold budget for the PoC iteration phase with alerts at 50%, 90%, and 100%.
3. **Provision Database:** Deploy a cost-optimized Cloud SQL for PostgreSQL instance and enable the `pgvector` extension.
4. **Define Schema:** Write the SQL schema to ingest the JSON chunks we generated in Phase 1.

*To resume, simply tell the agent to "read PROGRESS.md and continue".*
