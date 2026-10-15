import os
import re
import json
import time
import urllib.request
import psycopg2
from psycopg2.extras import execute_batch
from pgvector.psycopg2 import register_vector
from google import genai
from google.genai import types

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "mtsbe_data")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "ChangeThisStrongPassword123!")

BSB_TABLES_URL = "https://bereanbible.com/bsb_tables.tsv"
BSB_JSON_URL = "https://raw.githubusercontent.com/amir-hanna/bible/master/bsb.json"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../.."))
RAW_DATA_DIR = os.path.join(PROJECT_ROOT, "data/raw")
PROCESSED_DATA_DIR = os.path.join(PROJECT_ROOT, "data/processed")

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

def fetch_bsb_headings_and_verses():
    """
    Streams bsb_tables.tsv to extract all Genesis verses and section headings.
    """
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    cache_file = os.path.join(RAW_DATA_DIR, "bsb_genesis_headings.json")
    
    if os.path.exists(cache_file):
        print(f"Loading cached BSB Genesis headings from {cache_file}...")
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
            
    print(f"Streaming Genesis headings from {BSB_TABLES_URL}...")
    req = urllib.request.Request(BSB_TABLES_URL, headers={"User-Agent": "Mozilla/5.0"})
    
    all_verses = []
    heading_map = {}
    current_verse = None
    
    with urllib.request.urlopen(req) as resp:
        header = resp.readline().decode("utf-8", errors="ignore").strip().split("\t")
        verse_idx = header.index("VerseId")
        hdg_idx = header.index("Hdg")
        
        for line in resp:
            parts = line.decode("utf-8", errors="ignore").split("\t")
            if len(parts) > verse_idx and parts[verse_idx].strip():
                current_verse = parts[verse_idx].strip()
                if not current_verse.startswith("Genesis "):
                    if all_verses:
                        break
                    continue
                if not all_verses or all_verses[-1] != current_verse:
                    all_verses.append(current_verse)
                    
            if len(parts) > hdg_idx and parts[hdg_idx].strip() and current_verse and current_verse.startswith("Genesis "):
                hdg = parts[hdg_idx].strip()
                clean_hdg = re.sub(r"<[^>]+>", "", hdg.replace("|", "<")).strip()
                clean_hdg = re.sub(r"<[^>]*$", "", clean_hdg).strip()
                if clean_hdg and current_verse not in heading_map:
                    heading_map[current_verse] = clean_hdg
                    
    payload = {
        "all_verses": all_verses,
        "heading_map": heading_map
    }
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        
    print(f"Extracted {len(all_verses)} verses and {len(heading_map)} headings. Saved cache to {cache_file}.")
    return payload

def load_bsb_verses_json():
    """
    Loads full BSB JSON for English verse text.
    """
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    cache_file = os.path.join(RAW_DATA_DIR, "bsb.json")
    
    if os.path.exists(cache_file):
        print(f"Loading cached BSB verses from {cache_file}...")
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        print(f"Downloading BSB JSON from {BSB_JSON_URL}...")
        req = urllib.request.Request(BSB_JSON_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
            
    raw_dict = data.get("_default", data)
    book_map = {}
    for item in raw_dict.values():
        b = item["book"]
        c = int(item["chapter"])
        v = int(item["verse"])
        t = item["text"]
        if b not in book_map:
            book_map[b] = {}
        if c not in book_map[b]:
            book_map[b][c] = {}
        book_map[b][c][v] = t
    return book_map

def build_granular_pericopes(bsb_data, english_book_map, existing_verses, existing_pericopes):
    """
    Builds the 148 granular pericope chunks from BSB headings and verse data.
    """
    all_verses = bsb_data["all_verses"]
    heading_map = bsb_data["heading_map"]
    hdg_keys = list(heading_map.keys())
    
    # Verse text lookups from DB
    hebrew_verse_map = {v["id"]: v["text"] for v in existing_verses}
    
    # Build old pericope midrash link map
    # We can check which old pericope had midrash links and re-attribute to the granular pericopes
    midrash_links_by_chapter = {}
    for p in existing_pericopes:
        ch = p.get("chapter_start")
        links = p.get("external_links", {})
        if isinstance(links, dict) and links.get("midrash"):
            midrash_links_by_chapter[ch] = links["midrash"]
            
    pericopes = []
    gen_english = english_book_map.get("Genesis", {})
    
    for i, start_v in enumerate(hdg_keys):
        start_idx = all_verses.index(start_v)
        if i + 1 < len(hdg_keys):
            next_start_v = hdg_keys[i + 1]
            end_idx = all_verses.index(next_start_v) - 1
            end_v = all_verses[end_idx]
        else:
            end_idx = len(all_verses) - 1
            end_v = all_verses[-1]
            
        m_start = re.match(r"Genesis (\d+):(\d+)", start_v)
        m_end = re.match(r"Genesis (\d+):(\d+)", end_v)
        c_start, v_start = int(m_start.group(1)), int(m_start.group(2))
        c_end, v_end = int(m_end.group(1)), int(m_end.group(2))
        
        verse_slice = all_verses[start_idx : end_idx + 1]
        child_ids = [f"gen-{v.split()[1].replace(':', '-')}" for v in verse_slice]
        
        pericope_id = f"gen-{c_start}-{v_start}-{c_end}-{v_end}-pericope" if c_start != c_end else f"gen-{c_start}-{v_start}-{v_end}-pericope"
        title = heading_map[start_v]
        
        # Assemble English text
        eng_parts = []
        for v_str in verse_slice:
            parts = v_str.split()[1].split(":")
            ch_num, vs_num = int(parts[0]), int(parts[1])
            verse_text = gen_english.get(ch_num, {}).get(vs_num, "")
            eng_parts.append(f"[{ch_num}:{vs_num}] {verse_text}")
        english_text = " ".join(eng_parts)
        
        # Assemble Hebrew text
        heb_parts = []
        for vid in child_ids:
            heb = hebrew_verse_map.get(vid, "")
            if heb:
                heb_parts.append(heb)
        hebrew_text = " ".join(heb_parts)
        
        # Midrash links: attach if chapter matches
        # (For chapter 2, attach the existing sample Midrash references)
        attached_midrash = []
        if c_start in midrash_links_by_chapter:
            attached_midrash = midrash_links_by_chapter[c_start]
            
        pericopes.append({
            "id": pericope_id,
            "type": "pericope",
            "corpus": "biblical",
            "book": "Genesis",
            "chapter_start": c_start,
            "verse_start": v_start,
            "chapter_end": c_end,
            "verse_end": v_end,
            "pericope_title": title,
            "text": hebrew_text,
            "english_text": english_text,
            "child_verse_ids": child_ids,
            "external_links": {
                "midrash": attached_midrash,
                "church_fathers": [],
                "secular": []
            }
        })
        
    # Handle versification difference: Gen 32:33 in Hebrew
    for p in pericopes:
        if p["id"] == "gen-32-22-32-pericope":
            if "gen-32-33" in hebrew_verse_map and "gen-32-33" not in p["child_verse_ids"]:
                p["child_verse_ids"].append("gen-32-33")
                p["text"] += " " + hebrew_verse_map.get("gen-32-33", "")

    return pericopes

def generate_pericope_embeddings(pericopes):
    """
    Generates 768-dim embeddings for each pericope using gemini-embedding-2 on Vertex AI.
    Embeds f"{title}: {english_text}" for optimal semantic alignment with user queries.
    """
    print("Initializing Vertex AI Client for embeddings...")
    client = genai.Client(vertexai=True, project="mtsbe-1208613", location="us")
    
    total = len(pericopes)
    for i, p in enumerate(pericopes):
        embed_content = f"{p['pericope_title']}: {p['english_text']}"
        if i % 10 == 0 or i == total - 1:
            print(f"Generating embedding {i + 1}/{total} for '{p['pericope_title']}' ({p['id']})...")
            
        max_retries = 3
        for attempt in range(max_retries):
            try:
                res = client.models.embed_content(
                    model="gemini-embedding-2",
                    contents=embed_content,
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_DOCUMENT",
                        output_dimensionality=768
                    )
                )
                p["embedding"] = res.embeddings[0].values
                break
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for {p['id']}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))
                else:
                    raise
                    
        time.sleep(0.05)
        
    print(f"Successfully generated embeddings for all {total} pericopes.")
    return pericopes

def update_database(conn, granular_pericopes, english_book_map):
    """
    Inserts 148 granular pericopes, updates verses' parent_pericope_id and english_text,
    and removes old chapter-level pericopes.
    """
    cur = conn.cursor()
    
    print(f"1. Upserting {len(granular_pericopes)} granular pericopes into 'pericopes' table...")
    insert_query = """
        INSERT INTO pericopes (
            id, type, corpus, book, chapter_start, verse_start, chapter_end, verse_end,
            pericope_title, text, english_text, child_verse_ids, external_links, embedding
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (id) DO UPDATE SET
            pericope_title = EXCLUDED.pericope_title,
            text = EXCLUDED.text,
            english_text = EXCLUDED.english_text,
            child_verse_ids = EXCLUDED.child_verse_ids,
            external_links = EXCLUDED.external_links,
            embedding = EXCLUDED.embedding;
    """
    
    pericope_records = []
    for p in granular_pericopes:
        pericope_records.append((
            p["id"], p["type"], p["corpus"], p["book"],
            p["chapter_start"], p["verse_start"], p["chapter_end"], p["verse_end"],
            p["pericope_title"], p["text"], p["english_text"], p["child_verse_ids"],
            json.dumps(p["external_links"]), p["embedding"]
        ))
        
    cur.executemany(insert_query, pericope_records)
    print("   Granular pericopes upserted successfully.")
    
    print("2. Updating verses table with parent_pericope_id and individual english_text...")
    verse_update_records = []
    gen_english = english_book_map.get("Genesis", {})
    
    for p in granular_pericopes:
        for vid in p["child_verse_ids"]:
            # vid: gen-18-1
            parts = vid.split("-")
            ch, vs = int(parts[1]), int(parts[2])
            eng_v_text = gen_english.get(ch, {}).get(vs, "")
            verse_update_records.append((p["id"], eng_v_text, vid))
            
    update_verse_query = """
        UPDATE verses
        SET parent_pericope_id = %s,
            english_text = %s
        WHERE id = %s;
    """
    execute_batch(cur, update_verse_query, verse_update_records, page_size=200)
    print(f"   Updated {len(verse_update_records)} verses with new parent IDs and English text.")
    
    # Handle gen-32-33 Hebrew versification explicitly
    cur.execute("""
        UPDATE verses
        SET parent_pericope_id = 'gen-32-22-32-pericope',
            english_text = (SELECT english_text FROM verses WHERE id = 'gen-32-32')
        WHERE id = 'gen-32-33';
    """)
    
    # Verify no verses reference obsolete pericopes
    new_pericope_ids = tuple(p["id"] for p in granular_pericopes)
    cur.execute("""
        SELECT id, parent_pericope_id FROM verses WHERE parent_pericope_id NOT IN %s;
    """, (new_pericope_ids,))
    dangling = cur.fetchall()
    if dangling:
        print(f"   Warning: Found dangling verses: {dangling}")
    
    print("3. Removing old chapter-level pericopes...")
    cur.execute("""
        DELETE FROM pericopes
        WHERE id NOT IN %s AND (book = 'Gen' OR book = 'Genesis');
    """, (new_pericope_ids,))
    deleted_count = cur.rowcount
    print(f"   Removed {deleted_count} obsolete chapter-level pericopes.")
    
    conn.commit()
    cur.close()
    print("Database update committed successfully!")

def main():
    print("=== Starting Granular Pericopes Ingestion ===")
    
    # 1. Fetch BSB headings
    bsb_data = fetch_bsb_headings_and_verses()
    
    # 2. Load BSB English verses
    english_book_map = load_bsb_verses_json()
    
    # 3. Connect to DB to fetch existing verse and pericope metadata
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, text FROM verses WHERE book = 'Gen' OR book = 'Genesis'")
    existing_verses = [{"id": r[0], "text": r[1]} for r in cur.fetchall()]
    
    cur.execute("SELECT id, chapter_start, external_links FROM pericopes")
    existing_pericopes = [{"id": r[0], "chapter_start": r[1], "external_links": r[2]} for r in cur.fetchall()]
    cur.close()
    
    print(f"Fetched {len(existing_verses)} existing verses and {len(existing_pericopes)} existing pericopes from DB.")
    
    # 4. Build granular pericopes
    granular_pericopes = build_granular_pericopes(
        bsb_data, english_book_map, existing_verses, existing_pericopes
    )
    print(f"Built {len(granular_pericopes)} granular pericopes.")
    
    # 5. Generate embeddings
    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)
    embedded_file = os.path.join(PROCESSED_DATA_DIR, "genesis_granular_embedded.json")
    
    if os.path.exists(embedded_file):
        print(f"Found cached granular embedded pericopes at {embedded_file}!")
        with open(embedded_file, "r", encoding="utf-8") as f:
            granular_pericopes = json.load(f)
    else:
        granular_pericopes = generate_pericope_embeddings(granular_pericopes)
        with open(embedded_file, "w", encoding="utf-8") as f:
            json.dump(granular_pericopes, f, indent=2, ensure_ascii=False)
        print(f"Saved embedded pericopes to {embedded_file}.")
        
    # 6. Update database
    update_database(conn, granular_pericopes, english_book_map)
    conn.close()
    
    print("=== Granular Pericopes Ingestion Complete ===")

if __name__ == "__main__":
    main()
