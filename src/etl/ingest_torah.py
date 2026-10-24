"""
ingest_torah.py
MTSBE ETL Pipeline: Canonical Torah Expansion

Ingests the remaining 4 books of the Torah:
1. Exodus (Shemot) - 1,213 verses, 123 granular pericopes
2. Leviticus (Vayikra) - 859 verses, 70 granular pericopes
3. Numbers (Bamidbar) - 1,288 verses, 113 granular pericopes
4. Deuteronomy (Devarim) - 959 verses, 91 granular pericopes

Combines:
- Morphological Hebrew Bible OSIS XML (authentic Hebrew text with vowels & cantillation)
- Berean Standard Bible (BSB) English translation
- Berean Standard Bible granular pericope headings and narrative boundaries
- Dense 768-dim vector embeddings via Vertex AI (gemini-embedding-2)

Upserts all 397 pericopes and 4,319 verses directly into Cloud SQL (mtsbe_data).
"""

import os
import re
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../.."))
RAW_DATA_DIR = os.path.join(PROJECT_ROOT, "data/raw")
PROCESSED_DATA_DIR = os.path.join(PROJECT_ROOT, "data/processed")

TORAH_EXPANSION_BOOKS = [
    {
        "name": "Exodus",
        "prefix": "exod",
        "xml_file": os.path.join(RAW_DATA_DIR, "Exod.xml")
    },
    {
        "name": "Leviticus",
        "prefix": "lev",
        "xml_file": os.path.join(RAW_DATA_DIR, "Lev.xml")
    },
    {
        "name": "Numbers",
        "prefix": "num",
        "xml_file": os.path.join(RAW_DATA_DIR, "Num.xml")
    },
    {
        "name": "Deuteronomy",
        "prefix": "deut",
        "xml_file": os.path.join(RAW_DATA_DIR, "Deut.xml")
    }
]

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

def parse_hebrew_verses(xml_path: str) -> dict[str, str]:
    """
    Parses MorphHB OSIS XML to extract raw Hebrew verse text.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    for elem in root.iter():
        if "}" in elem.tag:
            elem.tag = elem.tag.split("}", 1)[1]
            
    verses = {}
    for verse in root.findall(".//verse"):
        v_id = verse.get("osisID")
        if v_id:
            v_text = "".join(verse.itertext()).strip()
            # Normalize whitespace
            v_text = re.sub(r"\s+", " ", v_text)
            key = v_id.lower().replace(".", "-")
            verses[key] = v_text
    return verses

def remap_hebrew_id(book_name: str, key: str) -> str:
    """
    Reconciles Hebrew Masoretic versification numbering with Christian/BSB versification
    across known boundary shifts in Exodus, Leviticus, Numbers, and Deuteronomy.
    """
    parts = key.split("-")
    c, v = int(parts[1]), int(parts[2])
    
    if book_name == "Exodus":
        if c == 7 and 26 <= v <= 29:
            return f"exod-8-{v - 25}"
        if c == 8:
            return f"exod-8-{v + 4}"
        if c == 21 and v == 37:
            return "exod-22-1"
        if c == 22:
            return f"exod-22-{v + 1}"
    elif book_name == "Leviticus":
        if c == 5 and 20 <= v <= 26:
            return f"lev-6-{v - 19}"
        if c == 6:
            return f"lev-6-{v + 7}"
    elif book_name == "Numbers":
        if c == 17 and 1 <= v <= 15:
            return f"num-16-{v + 35}"
        if c == 17 and 16 <= v <= 28:
            return f"num-17-{v - 15}"
        if c == 30 and v == 1:
            return "num-29-40"
        if c == 30 and v > 1:
            return f"num-30-{v - 1}"
    elif book_name == "Deuteronomy":
        if c == 13 and v == 1:
            return "deut-12-32"
        if c == 13 and v > 1:
            return f"deut-13-{v - 1}"
        if c == 23 and v == 1:
            return "deut-22-30"
        if c == 23 and v > 1:
            return f"deut-23-{v - 1}"
        if c == 28 and v == 69:
            return "deut-29-1"
        if c == 29:
            return f"deut-29-{v + 1}"
            
    return key

def load_bsb_verses_json() -> dict[str, dict[int, dict[int, str]]]:
    """
    Loads full BSB JSON for English verse text.
    """
    bsb_json_path = os.path.join(RAW_DATA_DIR, "bsb.json")
    if not os.path.exists(bsb_json_path):
        raise FileNotFoundError(f"Missing {bsb_json_path}")
        
    with open(bsb_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    raw_dict = data.get("_default", data)
    book_map: dict[str, dict[int, dict[int, str]]] = {}
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

def extract_torah_headings_and_verses():
    """
    Reads data/raw/bsb_tables.tsv to extract verses and section headings for all Torah books.
    """
    tsv_path = os.path.join(RAW_DATA_DIR, "bsb_tables.tsv")
    cache_path = os.path.join(RAW_DATA_DIR, "bsb_torah_headings.json")
    
    if os.path.exists(cache_path):
        print(f"Loading cached Torah headings from {cache_path}...")
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
            
    print(f"Parsing Torah headings from {tsv_path}...")
    torah_names = [b["name"] for b in TORAH_EXPANSION_BOOKS]
    book_verses = {b: [] for b in torah_names}
    book_headings = {b: {} for b in torah_names}
    
    with open(tsv_path, "r", encoding="utf-8", errors="ignore") as f:
        header = f.readline().strip().split("\t")
        verse_idx = header.index("VerseId")
        hdg_idx = header.index("Hdg")
        
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) <= verse_idx:
                continue
            v_id = parts[verse_idx].strip()
            if not v_id:
                continue
                
            matched_book = None
            for b in torah_names:
                if v_id.startswith(b + " "):
                    matched_book = b
                    break
                    
            if not matched_book:
                if v_id.startswith("Joshua "):
                    break
                continue
                
            vl = book_verses[matched_book]
            if not vl or vl[-1] != v_id:
                vl.append(v_id)
                
            if len(parts) > hdg_idx and parts[hdg_idx].strip():
                raw_hdg = parts[hdg_idx].strip()
                clean_hdg = re.sub(r"<[^>]+>", "", raw_hdg.replace("|", "<")).strip()
                clean_hdg = re.sub(r"<[^>]*$", "", clean_hdg).strip()
                if clean_hdg and v_id not in book_headings[matched_book]:
                    book_headings[matched_book][v_id] = clean_hdg
                    
    payload = {
        "book_verses": book_verses,
        "book_headings": book_headings
    }
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        
    print(f"Extracted headings and verses for {len(torah_names)} books. Saved to {cache_path}.")
    return payload

def assemble_torah_pericopes_and_verses(torah_data, english_book_map):
    """
    Assembles pericopes and verse records across Exodus, Leviticus, Numbers, and Deuteronomy.
    """
    all_pericopes = []
    all_verses = []
    
    book_verses_dict = torah_data["book_verses"]
    book_headings_dict = torah_data["book_headings"]
    
    for book_info in TORAH_EXPANSION_BOOKS:
        b_name = book_info["name"]
        b_prefix = book_info["prefix"]
        xml_file = book_info["xml_file"]
        
        print(f"Processing {b_name}...")
        raw_hebrew = parse_hebrew_verses(xml_file)
        hebrew_verses = {}
        for k, v in raw_hebrew.items():
            remapped_k = remap_hebrew_id(b_name, k)
            hebrew_verses[remapped_k] = v
            
        b_english = english_book_map.get(b_name, {})
        vl = book_verses_dict[b_name]
        hdg_map = book_headings_dict[b_name]
        hdg_keys = list(hdg_map.keys())
        
        # Build Pericopes for this book
        book_pericopes = []
        for i, start_v in enumerate(hdg_keys):
            start_idx = vl.index(start_v)
            if i + 1 < len(hdg_keys):
                next_start_v = hdg_keys[i + 1]
                end_idx = vl.index(next_start_v) - 1
                end_v = vl[end_idx]
            else:
                end_idx = len(vl) - 1
                end_v = vl[-1]
                
            m_start = re.match(rf"{b_name} (\d+):(\d+)", start_v)
            m_end = re.match(rf"{b_name} (\d+):(\d+)", end_v)
            c_start, v_start = int(m_start.group(1)), int(m_start.group(2))
            c_end, v_end = int(m_end.group(1)), int(m_end.group(2))
            
            verse_slice = vl[start_idx : end_idx + 1]
            child_ids = [f"{b_prefix}-{v.split()[1].replace(':', '-')}" for v in verse_slice]
            
            pericope_id = f"{b_prefix}-{c_start}-{v_start}-{c_end}-{v_end}-pericope" if c_start != c_end else f"{b_prefix}-{c_start}-{v_start}-{v_end}-pericope"
            title = hdg_map[start_v]
            
            # English text assembly
            eng_parts = []
            for v_str in verse_slice:
                parts = v_str.split()[1].split(":")
                ch_num, vs_num = int(parts[0]), int(parts[1])
                verse_text = b_english.get(ch_num, {}).get(vs_num, "")
                eng_parts.append(f"[{ch_num}:{vs_num}] {verse_text}")
            english_text = " ".join(eng_parts)
            
            # Hebrew text assembly
            heb_parts = []
            for vid in child_ids:
                heb = hebrew_verses.get(vid, "")
                if heb:
                    heb_parts.append(heb)
            hebrew_text = " ".join(heb_parts)
            
            pericope_obj = {
                "id": pericope_id,
                "type": "pericope",
                "corpus": "biblical",
                "book": b_name,
                "chapter_start": c_start,
                "verse_start": v_start,
                "chapter_end": c_end,
                "verse_end": v_end,
                "pericope_title": title,
                "text": hebrew_text,
                "english_text": english_text,
                "child_verse_ids": child_ids,
                "external_links": {
                    "midrash": [],
                    "church_fathers": [],
                    "secular": []
                }
            }
            book_pericopes.append(pericope_obj)
            
            # Build individual verse records
            for vid in child_ids:
                parts = vid.split("-")
                ch_num, vs_num = int(parts[1]), int(parts[2])
                v_eng = b_english.get(ch_num, {}).get(vs_num, "")
                v_heb = hebrew_verses.get(vid, "")
                
                all_verses.append({
                    "id": vid,
                    "type": "verse",
                    "corpus": "biblical",
                    "book": b_name,
                    "chapter": ch_num,
                    "verse": vs_num,
                    "text": v_heb,
                    "english_text": v_eng,
                    "parent_pericope_id": pericope_id
                })
                
        print(f"  -> {b_name}: {len(book_pericopes)} pericopes, {len([v for v in all_verses if v['book'] == b_name])} verses.")
        all_pericopes.extend(book_pericopes)
        
    return all_pericopes, all_verses

def generate_pericope_embeddings(pericopes: list[dict]) -> list[dict]:
    """
    Generates 768-dim embeddings for each pericope using gemini-embedding-2 on Vertex AI.
    Embeds f"{book} - {title}: {english_text}" for optimal semantic alignment with user queries.
    """
    print(f"Initializing Vertex AI Client to embed {len(pericopes)} pericopes...")
    client = genai.Client(vertexai=True, project="mtsbe-1208613", location="us")
    
    total = len(pericopes)
    for i, p in enumerate(pericopes):
        embed_content = f"{p['book']} - {p['pericope_title']}: {p['english_text']}"
        if i % 25 == 0 or i == total - 1:
            print(f"Embedding {i + 1}/{total}: [{p['book']}] '{p['pericope_title']}' ({p['id']})...")
            
        max_retries = 4
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
                    time.sleep(3 * (attempt + 1))
                else:
                    raise
                    
        time.sleep(0.04)
        
    print(f"Successfully generated embeddings for all {total} pericopes.")
    return pericopes

def upsert_to_cloud_sql(conn, pericopes: list[dict], verses: list[dict]):
    """
    Upserts pericopes first (ensuring foreign key targets exist), then upserts verses.
    """
    cur = conn.cursor()
    
    print(f"1. Upserting {len(pericopes)} pericopes into Cloud SQL...")
    pericope_query = """
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
    
    pericope_records = [
        (
            p["id"], p["type"], p["corpus"], p["book"],
            p["chapter_start"], p["verse_start"], p["chapter_end"], p["verse_end"],
            p["pericope_title"], p["text"], p["english_text"], p["child_verse_ids"],
            json.dumps(p["external_links"]), p["embedding"]
        )
        for p in pericopes
    ]
    cur.executemany(pericope_query, pericope_records)
    print("   Pericopes upserted successfully.")
    
    print(f"2. Upserting {len(verses)} verses into Cloud SQL...")
    verse_query = """
        INSERT INTO verses (
            id, type, corpus, book, chapter, verse, text, english_text, parent_pericope_id
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (id) DO UPDATE SET
            text = EXCLUDED.text,
            english_text = EXCLUDED.english_text,
            parent_pericope_id = EXCLUDED.parent_pericope_id;
    """
    
    verse_records = [
        (
            v["id"], v["type"], v["corpus"], v["book"],
            v["chapter"], v["verse"], v["text"], v["english_text"],
            v["parent_pericope_id"]
        )
        for v in verses
    ]
    execute_batch(cur, verse_query, verse_records, page_size=250)
    print("   Verses upserted successfully.")
    
    conn.commit()
    cur.close()
    print("Cloud SQL transaction committed successfully!")

def main():
    print("==================================================")
    print("=== MTSBE Canonical Torah Expansion ETL (Exod - Deut) ===")
    print("==================================================")
    
    # 1. Extract headings and verse lists
    torah_data = extract_torah_headings_and_verses()
    
    # 2. Load BSB English text
    english_book_map = load_bsb_verses_json()
    
    # 3. Assemble pericopes and verses
    pericopes, verses = assemble_torah_pericopes_and_verses(torah_data, english_book_map)
    print(f"\nTotal assembled: {len(pericopes)} pericopes, {len(verses)} verses.")
    
    # 4. Generate or load embeddings
    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)
    embedded_cache = os.path.join(PROCESSED_DATA_DIR, "torah_expansion_embedded.json")
    
    if os.path.exists(embedded_cache):
        print(f"Loading cached embedded pericopes from {embedded_cache}...")
        with open(embedded_cache, "r", encoding="utf-8") as f:
            pericopes = json.load(f)
    else:
        pericopes = generate_pericope_embeddings(pericopes)
        with open(embedded_cache, "w", encoding="utf-8") as f:
            json.dump(pericopes, f, indent=2, ensure_ascii=False)
        print(f"Saved embedded pericopes to {embedded_cache}.")
        
    # 5. Upsert to Cloud SQL
    conn = get_db_connection()
    upsert_to_cloud_sql(conn, pericopes, verses)
    
    # 6. Verify row counts and integrity
    cur = conn.cursor()
    cur.execute("SELECT book, count(*) FROM pericopes GROUP BY book ORDER BY book;")
    print("\nDatabase Pericopes Summary:")
    for b, c in cur.fetchall():
        print(f"  • {b}: {c} pericopes")
        
    cur.execute("SELECT book, count(*) FROM verses GROUP BY book ORDER BY book;")
    print("\nDatabase Verses Summary:")
    for b, c in cur.fetchall():
        print(f"  • {b}: {c} verses")
        
    cur.close()
    conn.close()
    print("\n=== Canonical Torah Expansion Successfully Completed ===")

if __name__ == "__main__":
    main()
