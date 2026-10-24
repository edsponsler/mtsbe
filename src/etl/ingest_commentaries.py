"""
ingest_commentaries.py
MTSBE ETL Pipeline for Non-Biblical Commentaries and Historical Corpora

Ingests three parallel historical/theological traditions for Genesis:
1. Tradition: Historical - Flavius Josephus (Antiquities of the Jews, Book 1)
2. Tradition: Midrash - Genesis Rabbah / Bereshit Rabbah (Dual Hebrew + English from Sefaria API)
3. Tradition: Patristic - St. Augustine of Hippo (City of God, Books 15 & 16)

Generates 768-dim embeddings via Vertex AI (gemini-embedding-2) and upserts into
the PostgreSQL `commentaries` table with HNSW indexing.
"""

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

def clean_html(text: str) -> str:
    cleanr = re.compile(r"<.*?>")
    text = re.sub(cleanr, "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# =========================================================================
# 1. FLAVIUS JOSEPHUS: Antiquities of the Jews (Book 1)
# =========================================================================

JOSEPHUS_CHAPTER_MAPPINGS = [
    {
        "chapter_num": 1,
        "title": "Creation of the World and Origin of Man",
        "book": "Genesis",
        "c_start": 1, "v_start": 1, "c_end": 3, "v_end": 24,
        "linked_pericopes": ["gen-1-1-2-3-pericope", "gen-2-4-25-pericope", "gen-3-1-24-pericope"],
    },
    {
        "chapter_num": 2,
        "title": "Concerning the Posterity of Adam, and the Fall of Cain",
        "book": "Genesis",
        "c_start": 4, "v_start": 1, "c_end": 5, "v_end": 32,
        "linked_pericopes": ["gen-4-1-16-pericope", "gen-4-17-26-pericope", "gen-5-1-32-pericope"],
    },
    {
        "chapter_num": 3,
        "title": "Concerning the Flood and Noah's Ark",
        "book": "Genesis",
        "c_start": 6, "v_start": 1, "c_end": 9, "v_end": 29,
        "linked_pericopes": ["gen-6-1-8-pericope", "gen-6-9-22-pericope", "gen-7-1-24-pericope", "gen-8-1-22-pericope", "gen-9-1-17-pericope"],
    },
    {
        "chapter_num": 4,
        "title": "Concerning the Tower of Babel, and the Confusion of Tongues",
        "book": "Genesis",
        "c_start": 11, "v_start": 1, "c_end": 11, "v_end": 9,
        "linked_pericopes": ["gen-11-1-9-pericope"],
    },
    {
        "chapter_num": 7,
        "title": "How Abram our Forefather went out of the Land of the Chaldeans into Canaan",
        "book": "Genesis",
        "c_start": 12, "v_start": 1, "c_end": 12, "v_end": 9,
        "linked_pericopes": ["gen-12-1-9-pericope"],
    },
    {
        "chapter_num": 8,
        "title": "That When There was a Famine in Canaan, Abram Went Thence into Egypt",
        "book": "Genesis",
        "c_start": 12, "v_start": 10, "c_end": 13, "v_end": 18,
        "linked_pericopes": ["gen-12-10-20-pericope", "gen-13-1-18-pericope"],
    },
    {
        "chapter_num": 10,
        "title": "How Abram Overcame the Assyrians, and Encountered Melchizedek",
        "book": "Genesis",
        "c_start": 14, "v_start": 1, "c_end": 14, "v_end": 24,
        "linked_pericopes": ["gen-14-1-16-pericope", "gen-14-17-24-pericope"],
    },
    {
        "chapter_num": 11,
        "title": "How God Appeared to Abraham: The Three Angels at Mamre and the Destruction of Sodom",
        "book": "Genesis",
        "c_start": 18, "v_start": 1, "c_end": 19, "v_end": 38,
        "linked_pericopes": ["gen-18-1-15-pericope", "gen-18-16-33-pericope", "gen-19-1-29-pericope"],
    },
    {
        "chapter_num": 12,
        "title": "Concerning Isaac the Son of Abraham and the Expulsion of Hagar and Ishmael",
        "book": "Genesis",
        "c_start": 21, "v_start": 1, "c_end": 21, "v_end": 34,
        "linked_pericopes": ["gen-21-1-7-pericope", "gen-21-8-21-pericope"],
    },
    {
        "chapter_num": 13,
        "title": "Concerning Abraham's Faith: The Offering of Isaac on Mount Moriah",
        "book": "Genesis",
        "c_start": 22, "v_start": 1, "c_end": 22, "v_end": 24,
        "linked_pericopes": ["gen-22-1-19-pericope"],
    },
    {
        "chapter_num": 14,
        "title": "Concerning the Death and Burial of Sarah at Machpelah",
        "book": "Genesis",
        "c_start": 23, "v_start": 1, "c_end": 23, "v_end": 20,
        "linked_pericopes": ["gen-23-1-20-pericope"],
    },
    {
        "chapter_num": 16,
        "title": "How Isaac Took Rebekah to Wife",
        "book": "Genesis",
        "c_start": 24, "v_start": 1, "c_end": 24, "v_end": 67,
        "linked_pericopes": ["gen-24-1-67-pericope"],
    },
    {
        "chapter_num": 18,
        "title": "Concerning the Sons of Isaac, Esau and Jacob: The Birthright and the Blessing",
        "book": "Genesis",
        "c_start": 25, "v_start": 19, "c_end": 27, "v_end": 46,
        "linked_pericopes": ["gen-25-19-34-pericope", "gen-27-1-40-pericope"],
    },
    {
        "chapter_num": 19,
        "title": "Concerning Jacob's Flight into Mesopotamia and Ladder at Bethel",
        "book": "Genesis",
        "c_start": 28, "v_start": 10, "c_end": 31, "v_end": 55,
        "linked_pericopes": ["gen-28-10-22-pericope", "gen-29-1-30-pericope", "gen-31-1-55-pericope"],
    },
    {
        "chapter_num": 20,
        "title": "Concerning the Meeting of Jacob and Esau, and Wrestling at Peniel",
        "book": "Genesis",
        "c_start": 32, "v_start": 1, "c_end": 33, "v_end": 20,
        "linked_pericopes": ["gen-32-1-21-pericope", "gen-32-22-32-pericope", "gen-33-1-17-pericope"],
    }
]

def fetch_josephus_commentaries() -> list[dict]:
    print("Fetching Flavius Josephus (Antiquities Book 1) from Project Gutenberg...")
    url = "https://www.gutenberg.org/files/2848/2848-0.txt"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        text = resp.read().decode("utf-8", errors="ignore")

    body_start = 56690
    matches = [m.start() for m in re.finditer(r"BOOK\s+II\.", text)]
    body_end = [m for m in matches if m > body_start][0]
    book1_text = text[body_start:body_end]

    raw_chapters = re.split(r"\n+(?=CHAPTER\s+\d+\.)", book1_text)
    chapter_map = {}
    for ch in raw_chapters:
        m = re.match(r"CHAPTER\s+(\d+)\.\s*([^\n]+)", ch.strip())
        if m:
            c_num = int(m.group(1))
            chapter_map[c_num] = ch.strip()

    items = []
    for mapping in JOSEPHUS_CHAPTER_MAPPINGS:
        c_num = mapping["chapter_num"]
        ch_text = chapter_map.get(c_num)
        if not ch_text:
            continue

        # Split chapter into numbered paragraphs/sections (e.g., "1. In the beginning...", "2. Moses says...")
        sections = re.split(r"\n+(?=\d+\.\s+)", ch_text)
        header = sections[0].strip()
        body_sections = sections[1:] if len(sections) > 1 else [ch_text]

        # Combine into 1 or 2 cohesive narrative chunks per chapter (~400-800 words)
        combined_chunks = []
        curr_text = ""
        for sec in body_sections:
            sec_clean = clean_html(sec)
            if len(curr_text) + len(sec_clean) < 3000:
                curr_text += "\n\n" + sec_clean if curr_text else sec_clean
            else:
                combined_chunks.append(curr_text)
                curr_text = sec_clean
        if curr_text:
            combined_chunks.append(curr_text)

        for chunk_idx, chunk_text in enumerate(combined_chunks):
            cid = f"josephus-ant-1-{c_num}-{chunk_idx + 1}"
            ref_str = f"Antiquities of the Jews 1.{c_num}.{chunk_idx + 1}" if len(combined_chunks) > 1 else f"Antiquities of the Jews 1.{c_num}"
            items.append({
                "id": cid,
                "tradition": "historical",
                "author": "Flavius Josephus",
                "work": "Antiquities of the Jews",
                "reference": ref_str,
                "book": mapping["book"],
                "chapter_start": mapping["c_start"],
                "verse_start": mapping["v_start"],
                "chapter_end": mapping["c_end"],
                "verse_end": mapping["v_end"],
                "title": f"{mapping['title']} (Part {chunk_idx + 1})" if len(combined_chunks) > 1 else mapping["title"],
                "text": chunk_text,
                "original_language_text": None,
                "linked_pericope_ids": mapping["linked_pericopes"],
                "metadata": {"source": "Project Gutenberg #2848", "whiston_translation": True}
            })

    print(f"Extracted {len(items)} Josephus commentary chunks.")
    return items

# =========================================================================
# 2. JEWISH MIDRASH: Bereshit Rabbah (Sefaria API)
# =========================================================================

SEFARIA_MIDRASH_CHAPTERS = [
    {
        "ch": 1,
        "title": "Creation of the Primordial Light (Ohr HaGanuz)",
        "book": "Genesis",
        "c_start": 1, "v_start": 1, "c_end": 1, "v_end": 5,
        "linked_pericopes": ["gen-1-1-2-3-pericope"],
    },
    {
        "ch": 8,
        "title": "Creation of Humanity and Consultation with the Angels",
        "book": "Genesis",
        "c_start": 1, "v_start": 26, "c_end": 2, "v_end": 3,
        "linked_pericopes": ["gen-1-1-2-3-pericope"],
    },
    {
        "ch": 22,
        "title": "Cain and Abel: Offerings, the Dispute in the Field, and the Mark",
        "book": "Genesis",
        "c_start": 4, "v_start": 1, "c_end": 4, "v_end": 16,
        "linked_pericopes": ["gen-4-1-16-pericope"],
    },
    {
        "ch": 30,
        "title": "Noah, the Corrupt Generation, and the Commission of the Ark",
        "book": "Genesis",
        "c_start": 6, "v_start": 9, "c_end": 6, "v_end": 22,
        "linked_pericopes": ["gen-6-9-22-pericope"],
    },
    {
        "ch": 34,
        "title": "Noah Emerging from the Ark and the Covenant of the Rainbow",
        "book": "Genesis",
        "c_start": 9, "v_start": 1, "c_end": 9, "v_end": 17,
        "linked_pericopes": ["gen-9-1-17-pericope"],
    },
    {
        "ch": 38,
        "title": "The Generation of the Dispersion and the Tower of Babel",
        "book": "Genesis",
        "c_start": 11, "v_start": 1, "c_end": 11, "v_end": 9,
        "linked_pericopes": ["gen-11-1-9-pericope"],
    },
    {
        "ch": 39,
        "title": "The Call of Abram (Lech Lecha) and Migrations of Faith",
        "book": "Genesis",
        "c_start": 12, "v_start": 1, "c_end": 12, "v_end": 9,
        "linked_pericopes": ["gen-12-1-9-pericope"],
    },
    {
        "ch": 43,
        "title": "Abram Rescues Lot and Encounters Melchizedek",
        "book": "Genesis",
        "c_start": 14, "v_start": 1, "c_end": 14, "v_end": 24,
        "linked_pericopes": ["gen-14-1-16-pericope", "gen-14-17-24-pericope"],
    },
    {
        "ch": 44,
        "title": "The Covenant between the Parts (Brit Bein HaBetarim)",
        "book": "Genesis",
        "c_start": 15, "v_start": 1, "c_end": 15, "v_end": 21,
        "linked_pericopes": ["gen-15-1-21-pericope"],
    },
    {
        "ch": 48,
        "title": "The Three Visitors at the Plains of Mamre: Abraham's Hospitality and Circumcision",
        "book": "Genesis",
        "c_start": 18, "v_start": 1, "c_end": 18, "v_end": 15,
        "linked_pericopes": ["gen-18-1-15-pericope"],
    },
    {
        "ch": 49,
        "title": "Abraham's Intercession for the Righteous in Sodom",
        "book": "Genesis",
        "c_start": 18, "v_start": 16, "c_end": 18, "v_end": 33,
        "linked_pericopes": ["gen-18-16-33-pericope"],
    },
    {
        "ch": 53,
        "title": "The Birth of Isaac and the Celebration of the Covenant",
        "book": "Genesis",
        "c_start": 21, "v_start": 1, "c_end": 21, "v_end": 7,
        "linked_pericopes": ["gen-21-1-7-pericope"],
    },
    {
        "ch": 55,
        "title": "The Trial of Faith: God Tests Abraham for the Akedah",
        "book": "Genesis",
        "c_start": 22, "v_start": 1, "c_end": 22, "v_end": 4,
        "linked_pericopes": ["gen-22-1-19-pericope"],
    },
    {
        "ch": 56,
        "title": "The Akedah: Binding of Isaac on Mount Moriah and the Ram in the Thicket",
        "book": "Genesis",
        "c_start": 22, "v_start": 5, "c_end": 22, "v_end": 19,
        "linked_pericopes": ["gen-22-1-19-pericope"],
    },
    {
        "ch": 63,
        "title": "The Birth of Esau and Jacob: The Red Lentil Stew and the Sold Birthright",
        "book": "Genesis",
        "c_start": 25, "v_start": 19, "c_end": 25, "v_end": 34,
        "linked_pericopes": ["gen-25-19-34-pericope"],
    },
    {
        "ch": 68,
        "title": "Jacob's Dream at Bethel: Angels Ascending and Descending the Ladder",
        "book": "Genesis",
        "c_start": 28, "v_start": 10, "c_end": 28, "v_end": 22,
        "linked_pericopes": ["gen-28-10-22-pericope"],
    },
    {
        "ch": 77,
        "title": "Jacob Wrestles the Angel at Peniel (The Crossing of Jabbok)",
        "book": "Genesis",
        "c_start": 32, "v_start": 22, "c_end": 32, "v_end": 32,
        "linked_pericopes": ["gen-32-22-32-pericope"],
    }
]

def fetch_sefaria_midrash() -> list[dict]:
    print("Fetching Genesis Rabbah (Bereshit Rabbah) from Sefaria API...")
    items = []
    for info in SEFARIA_MIDRASH_CHAPTERS:
        ch_num = info["ch"]
        url = f"https://www.sefaria.org/api/texts/Bereshit_Rabbah.{ch_num}?context=0"
        req = urllib.request.Request(url, headers={"User-Agent": "MTSBE-Corpus-Engine/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            print(f"Warning: Failed to fetch Bereshit Rabbah {ch_num}: {e}")
            continue

        en_texts = data.get("text", [])
        he_texts = data.get("he", [])

        # Filter out empty or non-string sections
        valid_pairs = []
        for i in range(max(len(en_texts), len(he_texts))):
            en = clean_html(str(en_texts[i])) if i < len(en_texts) and en_texts[i] else ""
            he = clean_html(str(he_texts[i])) if i < len(he_texts) and he_texts[i] else ""
            if en or he:
                valid_pairs.append((i + 1, en, he))

        # Group sections into 1 to 3 substantive chunks per chapter
        chunk_size = 4
        for chunk_idx in range(0, len(valid_pairs), chunk_size):
            slice_pairs = valid_pairs[chunk_idx:chunk_idx + chunk_size]
            en_combined = "\n\n".join([f"[{ch_num}:{sec}] {en}" for sec, en, he in slice_pairs if en])
            he_combined = "\n\n".join([f"[{ch_num}:{sec}] {he}" for sec, en, he in slice_pairs if he])

            if not en_combined and not he_combined:
                continue

            sec_start = slice_pairs[0][0]
            sec_end = slice_pairs[-1][0]
            cid = f"sefaria-gen-rab-{ch_num}-{sec_start}-{sec_end}"
            ref_str = f"Genesis Rabbah {ch_num}:{sec_start}–{sec_end}" if sec_start != sec_end else f"Genesis Rabbah {ch_num}:{sec_start}"

            items.append({
                "id": cid,
                "tradition": "midrash",
                "author": "Genesis Rabbah",
                "work": "Midrash Rabbah",
                "reference": ref_str,
                "book": info["book"],
                "chapter_start": info["c_start"],
                "verse_start": info["v_start"],
                "chapter_end": info["c_end"],
                "verse_end": info["v_end"],
                "title": f"{info['title']} ({ref_str})",
                "text": en_combined if en_combined else he_combined,
                "original_language_text": he_combined if he_combined else None,
                "linked_pericope_ids": info["linked_pericopes"],
                "metadata": {"source": "Sefaria API", "hebrew_available": bool(he_combined)}
            })

    print(f"Extracted {len(items)} Bereshit Rabbah commentary chunks.")
    return items

# =========================================================================
# 3. PATRISTIC WRITINGS: Augustine of Hippo (City of God, Books 15 & 16)
# =========================================================================

AUGUSTINE_CHAPTER_MAPPINGS = [
    {
        "book_num": 15,
        "ch_num": 1,
        "title": "The Origin of the Two Cities: The Earthly City Founded by Cain and the Heavenly City Exemplified in Abel",
        "book": "Genesis",
        "c_start": 4, "v_start": 1, "c_end": 4, "v_end": 16,
        "linked_pericopes": ["gen-4-1-16-pericope"],
    },
    {
        "book_num": 15,
        "ch_num": 7,
        "title": "Cain's Malice and Unworthy Offering: The Distinction Between Deeds of the Flesh and True Righteousness",
        "book": "Genesis",
        "c_start": 4, "v_start": 3, "c_end": 4, "v_end": 8,
        "linked_pericopes": ["gen-4-1-16-pericope"],
    },
    {
        "book_num": 15,
        "ch_num": 17,
        "title": "Cain Building the First City: Temporal Fortification versus the Pilgrim Citizens of God",
        "book": "Genesis",
        "c_start": 4, "v_start": 17, "c_end": 4, "v_end": 24,
        "linked_pericopes": ["gen-4-17-26-pericope"],
    },
    {
        "book_num": 15,
        "ch_num": 26,
        "title": "Noah's Ark as a Figure of the City of God and the Church: Typology of Wood and Proportions of the Human Body",
        "book": "Genesis",
        "c_start": 6, "v_start": 13, "c_end": 6, "v_end": 22,
        "linked_pericopes": ["gen-6-9-22-pericope"],
    },
    {
        "book_num": 16,
        "ch_num": 4,
        "title": "The Origin of the Tower of Babel: The Arrogant Ambition of the Earthly City",
        "book": "Genesis",
        "c_start": 11, "v_start": 1, "c_end": 11, "v_end": 9,
        "linked_pericopes": ["gen-11-1-9-pericope"],
    },
    {
        "book_num": 16,
        "ch_num": 12,
        "title": "The Call of Abraham and the Separation from Idolatry: The Era of Divine Promises",
        "book": "Genesis",
        "c_start": 12, "v_start": 1, "c_end": 12, "v_end": 9,
        "linked_pericopes": ["gen-12-1-9-pericope"],
    },
    {
        "book_num": 16,
        "ch_num": 22,
        "title": "The Priesthood of Melchizedek: The Bread and Wine as the Archetype of the Sacramental Eucharist",
        "book": "Genesis",
        "c_start": 14, "v_start": 17, "c_end": 14, "v_end": 24,
        "linked_pericopes": ["gen-14-17-24-pericope"],
    },
    {
        "book_num": 16,
        "ch_num": 26,
        "title": "The Covenant of Circumcision Given to Abraham: The Mystery of Spiritual Regeneration",
        "book": "Genesis",
        "c_start": 17, "v_start": 1, "c_end": 17, "v_end": 27,
        "linked_pericopes": ["gen-17-1-27-pericope"],
    },
    {
        "book_num": 16,
        "ch_num": 29,
        "title": "The Three Men at the Oak of Mamre: Abraham Welcoming the Divine Visitors and Prophesying Sarah's Son",
        "book": "Genesis",
        "c_start": 18, "v_start": 1, "c_end": 18, "v_end": 15,
        "linked_pericopes": ["gen-18-1-15-pericope"],
    },
    {
        "book_num": 16,
        "ch_num": 32,
        "title": "The Offering of Isaac on Mount Moriah: Isaac Carrying the Wood as a Figure of Christ and the Ram in the Bush",
        "book": "Genesis",
        "c_start": 22, "v_start": 1, "c_end": 22, "v_end": 19,
        "linked_pericopes": ["gen-22-1-19-pericope"],
    },
    {
        "book_num": 16,
        "ch_num": 35,
        "title": "The Divine Oracle of Jacob and Esau: The Mystery of the Two Nations and the Elder Serving the Younger",
        "book": "Genesis",
        "c_start": 25, "v_start": 19, "c_end": 25, "v_end": 34,
        "linked_pericopes": ["gen-25-19-34-pericope"],
    },
    {
        "book_num": 16,
        "ch_num": 38,
        "title": "Jacob's Dream at Bethel: The Stone Anointed with Oil as the Prophetic Figure of Christ",
        "book": "Genesis",
        "c_start": 28, "v_start": 10, "c_end": 28, "v_end": 22,
        "linked_pericopes": ["gen-28-10-22-pericope"],
    }
]

def fetch_augustine_patristics() -> list[dict]:
    print("Fetching St. Augustine (City of God Books 15 & 16) from Project Gutenberg...")
    url = "https://www.gutenberg.org/files/45305/45305-0.txt"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        text = resp.read().decode("utf-8", errors="ignore")

    # Locate Book 15 and Book 16 start and end positions
    m15 = re.search(r"BOOK\s+FIFTEENTH\.", text)
    m16 = re.search(r"BOOK\s+SIXTEENTH\.", text)
    m17 = re.search(r"BOOK\s+SEVENTEENTH\.", text)

    book15_text = text[m15.start():m16.start()] if m15 and m16 else ""
    book16_text = text[m16.start():m17.start()] if m16 and m17 else ""

    def parse_book_chapters(book_text: str) -> dict[int, str]:
        pattern = r"\n\s*(\d+)\.\s*_([^_]+)_\s*\n(.*?)(?=\n\s*\d+\.\s*_[^_]+_\s*\n|\Z)"
        result = {}
        for m in re.finditer(pattern, book_text, re.DOTALL):
            c_num = int(m.group(1))
            body = clean_html(m.group(3))
            result[c_num] = body
        return result

    b15_map = parse_book_chapters(book15_text)
    b16_map = parse_book_chapters(book16_text)

    items = []
    for info in AUGUSTINE_CHAPTER_MAPPINGS:
        b_num = info["book_num"]
        c_num = info["ch_num"]
        ch_text = b15_map.get(c_num) if b_num == 15 else b16_map.get(c_num)

        if not ch_text:
            print(f"Warning: Chapter {c_num} in Book {b_num} not matched.")
            continue

        cid = f"patristic-augustine-city-of-god-{b_num}-{c_num}"
        ref_str = f"Augustine, City of God {b_num}.{c_num}"
        items.append({
            "id": cid,
            "tradition": "patristic",
            "author": "Augustine of Hippo",
            "work": "The City of God",
            "reference": ref_str,
            "book": info["book"],
            "chapter_start": info["c_start"],
            "verse_start": info["v_start"],
            "chapter_end": info["c_end"],
            "verse_end": info["v_end"],
            "title": f"{info['title']} ({ref_str})",
            "text": ch_text[:3500],  # Ensure appropriate chunk size
            "original_language_text": None,
            "linked_pericope_ids": info["linked_pericopes"],
            "metadata": {"source": "Project Gutenberg #45305", "marcus_dods_translation": True}
        })

    print(f"Extracted {len(items)} Augustine Patristic commentary chunks.")
    return items

# =========================================================================
# 4. EMBEDDING & DATABASE UPSERT
# =========================================================================

def embed_commentaries(commentaries: list[dict]):
    print(f"Generating 768-dim embeddings for {len(commentaries)} commentary chunks via Vertex AI (gemini-embedding-2)...")
    ai_client = genai.Client(vertexai=True, project="mtsbe-1208613", location="us")

    total = len(commentaries)
    for i, item in enumerate(commentaries):
        content_to_embed = f"[{item['tradition'].upper()} | {item['author']} - {item['reference']}]: {item['title']}\n\n{item['text'][:1500]}"
        if i % 10 == 0 or i == total - 1:
            print(f"Embedding {i + 1}/{total} ({item['tradition']}: {item['id']})...")

        for attempt in range(3):
            try:
                res = ai_client.models.embed_content(
                    model="gemini-embedding-2",
                    contents=content_to_embed,
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_DOCUMENT",
                        output_dimensionality=768
                    )
                )
                item["embedding"] = res.embeddings[0].values
                break
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for {item['id']}: {e}")
                time.sleep(2 * (attempt + 1))

def upsert_commentaries_to_db(commentaries: list[dict]):
    print(f"Upserting {len(commentaries)} commentary chunks into Cloud SQL `commentaries` table...")
    conn = get_db_connection()
    cur = conn.cursor()

    sql = """
        INSERT INTO commentaries (
            id, tradition, author, work, reference, book,
            chapter_start, verse_start, chapter_end, verse_end,
            title, text, original_language_text, linked_pericope_ids,
            metadata, embedding
        )
        VALUES (
            %(id)s, %(tradition)s, %(author)s, %(work)s, %(reference)s, %(book)s,
            %(chapter_start)s, %(verse_start)s, %(chapter_end)s, %(verse_end)s,
            %(title)s, %(text)s, %(original_language_text)s, %(linked_pericope_ids)s,
            %(metadata)s, %(embedding)s
        )
        ON CONFLICT (id) DO UPDATE SET
            tradition = EXCLUDED.tradition,
            author = EXCLUDED.author,
            work = EXCLUDED.work,
            reference = EXCLUDED.reference,
            book = EXCLUDED.book,
            chapter_start = EXCLUDED.chapter_start,
            verse_start = EXCLUDED.verse_start,
            chapter_end = EXCLUDED.chapter_end,
            verse_end = EXCLUDED.verse_end,
            title = EXCLUDED.title,
            text = EXCLUDED.text,
            original_language_text = EXCLUDED.original_language_text,
            linked_pericope_ids = EXCLUDED.linked_pericope_ids,
            metadata = EXCLUDED.metadata,
            embedding = EXCLUDED.embedding;
    """

    # Prepare data for execute_batch
    batch_params = []
    for c in commentaries:
        batch_params.append({
            "id": c["id"],
            "tradition": c["tradition"],
            "author": c["author"],
            "work": c["work"],
            "reference": c["reference"],
            "book": c["book"],
            "chapter_start": c["chapter_start"],
            "verse_start": c["verse_start"],
            "chapter_end": c["chapter_end"],
            "verse_end": c["verse_end"],
            "title": c["title"],
            "text": c["text"],
            "original_language_text": c["original_language_text"],
            "linked_pericope_ids": c["linked_pericope_ids"],
            "metadata": json.dumps(c["metadata"]),
            "embedding": c.get("embedding")
        })

    execute_batch(cur, sql, batch_params, page_size=50)
    conn.commit()

    cur.execute("SELECT tradition, COUNT(*) FROM commentaries GROUP BY tradition;")
    counts = cur.fetchall()
    print("Database Commentary Counts by Tradition:")
    for trad, count in counts:
        print(f"  • {trad.capitalize()}: {count} records")

    cur.close()
    conn.close()

def main():
    print("=== STARTING MTSBE MULTI-TRADITION CORPUS INGESTION ===")
    all_commentaries = []

    # 1. Flavius Josephus
    josephus_items = fetch_josephus_commentaries()
    all_commentaries.extend(josephus_items)

    # 2. Sefaria Midrash
    midrash_items = fetch_sefaria_midrash()
    all_commentaries.extend(midrash_items)

    # 3. Augustine Patristics
    patristic_items = fetch_augustine_patristics()
    all_commentaries.extend(patristic_items)

    print(f"\nTotal Commentary Chunks to Ingest: {len(all_commentaries)}")

    # Embed all chunks
    embed_commentaries(all_commentaries)

    # Save local JSON backup
    backup_path = os.path.join(os.path.dirname(__file__), "../../data/processed/commentaries_embedded.json")
    print(f"Saving embedded commentaries backup to {backup_path}...")
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(all_commentaries, f, indent=2)

    # Upsert to PostgreSQL
    upsert_commentaries_to_db(all_commentaries)
    print("=== MTSBE MULTI-TRADITION CORPUS INGESTION COMPLETE ===")

if __name__ == "__main__":
    main()
