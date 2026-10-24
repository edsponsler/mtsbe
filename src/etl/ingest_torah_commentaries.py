"""
ingest_torah_commentaries.py
MTSBE ETL Pipeline: Multi-Tradition Commentary Expansion for Exodus through Deuteronomy

Ingests three rich historical and theological traditions covering the entire Torah:
1. Historical Tradition: Flavius Josephus (Antiquities of the Jews, Books 2, 3, and 4)
   - Covers Moses in Egypt, the Burning Bush, Ten Plagues, Red Sea, Mount Sinai, Tabernacle,
     Wilderness, Korah's rebellion, Bronze Serpent, Balaam, and the Death of Moses.
2. Midrashic Tradition: Midrash Rabbah (Shemot, Vayikra, Bamidbar, Devarim) via Sefaria API
   - Dual Hebrew and English text on the key narrative inflection points of the Torah.
3. Patristic / Philosophical Tradition: Philo of Alexandria (The Life of Moses / De Vita Mosis)
   - Foundational allegorical and theological treatises on the Burning Bush, the Plagues,
     the Red Sea, Mount Sinai, the Tabernacle Archetypes, and Moses's Divine Passing.

Generates 768-dim dense embeddings via Vertex AI (gemini-embedding-2) and upserts
into Cloud SQL's `commentaries` table with HNSW vector indexing.
"""

import os
import re
import json
import time
import urllib.request
import psycopg2
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

def clean_html(text: str) -> str:
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL)
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL)
    text = re.sub(r"<.*?>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# =========================================================================
# 1. FLAVIUS JOSEPHUS: Antiquities of the Jews (Books 2, 3, and 4)
# =========================================================================

JOSEPHUS_TORAH_CHAPTERS = [
    # Book II (Exodus 1–15)
    {
        "book_num": 2, "ch_num": 9,
        "title": "The Afflictions of the Hebrews in Egypt, the Birth, and Childhood of Moses",
        "book": "Exodus", "c_start": 1, "v_start": 8, "c_end": 2, "v_end": 22,
        "linked_pericopes": ["exod-1-8-22-pericope", "exod-2-1-10-pericope", "exod-2-11-25-pericope"]
    },
    {
        "book_num": 2, "ch_num": 12,
        "title": "Concerning the Burning Bush on Mount Sinai and the Divine Name Revealed",
        "book": "Exodus", "c_start": 3, "v_start": 1, "c_end": 4, "v_end": 17,
        "linked_pericopes": ["exod-3-1-22-pericope", "exod-4-1-17-pericope"]
    },
    {
        "book_num": 2, "ch_num": 14,
        "title": "Concerning the Ten Plagues Inflicted Upon Pharaoh and the Egyptians",
        "book": "Exodus", "c_start": 7, "v_start": 14, "c_end": 11, "v_end": 10,
        "linked_pericopes": ["exod-7-14-25-pericope", "exod-10-1-20-pericope", "exod-11-1-10-pericope"]
    },
    {
        "book_num": 2, "ch_num": 15,
        "title": "The Institution of the Passover and the Exodus of the Hebrew Multitude",
        "book": "Exodus", "c_start": 12, "v_start": 1, "c_end": 13, "v_end": 22,
        "linked_pericopes": ["exod-12-1-28-pericope", "exod-13-17-22-pericope"]
    },
    {
        "book_num": 2, "ch_num": 16,
        "title": "The Miraculous Crossing of the Red Sea and Destruction of Pharaoh's Army",
        "book": "Exodus", "c_start": 14, "v_start": 1, "c_end": 15, "v_end": 21,
        "linked_pericopes": ["exod-14-1-31-pericope", "exod-15-1-21-pericope"]
    },
    # Book III (Exodus 16–40 & Leviticus)
    {
        "book_num": 3, "ch_num": 1,
        "title": "The Bitter Waters of Marah Sweetened and the Gift of Manna from Heaven",
        "book": "Exodus", "c_start": 15, "v_start": 22, "c_end": 16, "v_end": 36,
        "linked_pericopes": ["exod-15-22-27-pericope", "exod-16-1-36-pericope"]
    },
    {
        "book_num": 3, "ch_num": 2,
        "title": "The Battle Against the Amalekites and the Raised Hands of Moses",
        "book": "Exodus", "c_start": 17, "v_start": 8, "c_end": 17, "v_end": 16,
        "linked_pericopes": ["exod-17-8-16-pericope"]
    },
    {
        "book_num": 3, "ch_num": 5,
        "title": "Moses Ascends Mount Sinai Amid Thunder and Receives the Ten Commandments",
        "book": "Exodus", "c_start": 19, "v_start": 1, "c_end": 20, "v_end": 21,
        "linked_pericopes": ["exod-19-1-25-pericope", "exod-20-1-21-pericope"]
    },
    {
        "book_num": 3, "ch_num": 6,
        "title": "The Construction of the Tabernacle, the Holy Ark, and the Golden Menorah",
        "book": "Exodus", "c_start": 25, "v_start": 1, "c_end": 27, "v_end": 21,
        "linked_pericopes": ["exod-25-1-40-pericope", "exod-26-1-37-pericope"]
    },
    {
        "book_num": 3, "ch_num": 8,
        "title": "The Consecration of Aaron the High Priest and the Sacrificial Vestments",
        "book": "Exodus", "c_start": 28, "v_start": 1, "c_end": 29, "v_end": 46,
        "linked_pericopes": ["exod-28-1-5-pericope", "exod-29-1-46-pericope"]
    },
    {
        "book_num": 3, "ch_num": 10,
        "title": "The Sacrificial Feasts, the Passover, and the Day of Atonement",
        "book": "Leviticus", "c_start": 16, "v_start": 1, "c_end": 16, "v_end": 34,
        "linked_pericopes": ["lev-16-1-34-pericope"]
    },
    {
        "book_num": 3, "ch_num": 12,
        "title": "The Laws of Purity, Dietary Sanctity, and Holiness of the Priesthood",
        "book": "Leviticus", "c_start": 19, "v_start": 1, "c_end": 19, "v_end": 37,
        "linked_pericopes": ["lev-19-1-37-pericope"]
    },
    # Book IV (Numbers & Deuteronomy)
    {
        "book_num": 4, "ch_num": 2,
        "title": "The Sedition of Korah, Dathan, and Abiram Against Moses and Aaron",
        "book": "Numbers", "c_start": 16, "v_start": 1, "c_end": 16, "v_end": 35,
        "linked_pericopes": ["num-16-1-35-pericope"]
    },
    {
        "book_num": 4, "ch_num": 3,
        "title": "The Earth Opens to Swallow the Rebels and Aaron's Rod Blossoms",
        "book": "Numbers", "c_start": 16, "v_start": 36, "c_end": 17, "v_end": 13,
        "linked_pericopes": ["num-16-36-50-pericope", "num-17-1-13-pericope"]
    },
    {
        "book_num": 4, "ch_num": 4,
        "title": "The Sin at Meribah, the Bronze Serpent Lifted, and the Death of Aaron",
        "book": "Numbers", "c_start": 20, "v_start": 1, "c_end": 21, "v_end": 9,
        "linked_pericopes": ["num-20-1-13-pericope", "num-21-4-9-pericope"]
    },
    {
        "book_num": 4, "ch_num": 6,
        "title": "The History of Balaam the Prophet and his Involuntary Blessing of Israel",
        "book": "Numbers", "c_start": 22, "v_start": 1, "c_end": 24, "v_end": 25,
        "linked_pericopes": ["num-22-1-41-pericope", "num-23-1-30-pericope", "num-24-1-25-pericope"]
    },
    {
        "book_num": 4, "ch_num": 8,
        "title": "Moses's Farewell Discourse, the Renewal of the Covenant, and his Holy Passing on Mount Nebo",
        "book": "Deuteronomy", "c_start": 31, "v_start": 1, "c_end": 34, "v_end": 12,
        "linked_pericopes": ["deut-31-1-8-pericope", "deut-32-1-43-pericope", "deut-34-1-12-pericope"]
    }
]

def fetch_josephus_torah_commentaries() -> list[dict]:
    print("Fetching Josephus Books 2, 3, and 4 from Project Gutenberg #2848...")
    url = "https://www.gutenberg.org/files/2848/2848-0.txt"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        text = resp.read().decode("utf-8", errors="ignore")

    offsets = {
        "BOOK II.": 194257,
        "BOOK III.": 341544,
        "BOOK IV.": 478905,
        "BOOK V.": 621736
    }

    books_text = {
        2: text[offsets["BOOK II."]:offsets["BOOK III."]],
        3: text[offsets["BOOK III."]:offsets["BOOK IV."]],
        4: text[offsets["BOOK IV."]:offsets["BOOK V."]]
    }

    chapter_maps = {}
    for b_num, b_text in books_text.items():
        raw_chs = re.split(r"\n+(?=CHAPTER\s+\d+\.)", b_text)
        b_map = {}
        for ch in raw_chs:
            m = re.match(r"CHAPTER\s+(\d+)\.\s*([^\n]+)", ch.strip())
            if m:
                c_num = int(m.group(1))
                b_map[c_num] = ch.strip()
        chapter_maps[b_num] = b_map

    items = []
    for mapping in JOSEPHUS_TORAH_CHAPTERS:
        b_num = mapping["book_num"]
        c_num = mapping["ch_num"]
        ch_text = chapter_maps.get(b_num, {}).get(c_num)
        if not ch_text:
            print(f"Warning: Josephus Book {b_num} Chapter {c_num} not found!")
            continue

        sections = re.split(r"\n\s*\d+\.\s+", ch_text)
        body_sections = sections[1:] if len(sections) > 1 else [ch_text]

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
            cid = f"josephus-ant-{b_num}-{c_num}-{chunk_idx + 1}"
            ref_str = f"Antiquities of the Jews {b_num}.{c_num}.{chunk_idx + 1}" if len(combined_chunks) > 1 else f"Antiquities of the Jews {b_num}.{c_num}"
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
                "metadata": {"source": "Project Gutenberg #2848", "book": b_num, "chapter": c_num}
            })

    print(f"Extracted {len(items)} Josephus commentary chunks for Torah.")
    return items

# =========================================================================
# 2. JEWISH MIDRASH: Midrash Rabbah (Sefaria API)
# =========================================================================

SEFARIA_TORAH_MIDRASH = [
    # Shemot Rabbah (Exodus)
    {
        "ref": "Shemot_Rabbah.1", "name": "Shemot Rabbah 1",
        "title": "Moses Hidden in the Papyrus Basket and Adopted by Pharaoh's Daughter",
        "book": "Exodus", "c_start": 2, "v_start": 1, "c_end": 2, "v_end": 10,
        "linked_pericopes": ["exod-2-1-10-pericope"]
    },
    {
        "ref": "Shemot_Rabbah.2", "name": "Shemot Rabbah 2",
        "title": "The Compassion of Moses: The Lost Kid Carried to the Spring",
        "book": "Exodus", "c_start": 3, "v_start": 1, "c_end": 3, "v_end": 6,
        "linked_pericopes": ["exod-3-1-22-pericope"]
    },
    {
        "ref": "Shemot_Rabbah.3", "name": "Shemot Rabbah 3",
        "title": "The Revelation at the Burning Bush: The Divine Name Ehyeh Asher Ehyeh",
        "book": "Exodus", "c_start": 3, "v_start": 2, "c_end": 3, "v_end": 14,
        "linked_pericopes": ["exod-3-1-22-pericope"]
    },
    {
        "ref": "Shemot_Rabbah.21", "name": "Shemot Rabbah 21",
        "title": "The Splitting of the Sea of Reeds and the Leaping Faith of Nahshon",
        "book": "Exodus", "c_start": 14, "v_start": 15, "c_end": 14, "v_end": 31,
        "linked_pericopes": ["exod-14-1-31-pericope"]
    },
    {
        "ref": "Shemot_Rabbah.28", "name": "Shemot Rabbah 28",
        "title": "The Giving of the Torah at Mount Sinai: Cosmic Silence and Divine Utterance",
        "book": "Exodus", "c_start": 20, "v_start": 1, "c_end": 20, "v_end": 17,
        "linked_pericopes": ["exod-20-1-21-pericope"]
    },
    # Vayikra Rabbah (Leviticus)
    {
        "ref": "Vayikra_Rabbah.1", "name": "Vayikra Rabbah 1",
        "title": "The Divine Calling from the Tent of Meeting: The Humility of Moses",
        "book": "Leviticus", "c_start": 1, "v_start": 1, "c_end": 1, "v_end": 2,
        "linked_pericopes": ["lev-1-1-2-pericope"]
    },
    {
        "ref": "Vayikra_Rabbah.21", "name": "Vayikra Rabbah 21",
        "title": "The Day of Atonement (Yom Kippur) and the Scapegoat Bearing Israel's Sins",
        "book": "Leviticus", "c_start": 16, "v_start": 1, "c_end": 16, "v_end": 22,
        "linked_pericopes": ["lev-16-1-34-pericope"]
    },
    {
        "ref": "Vayikra_Rabbah.24", "name": "Vayikra Rabbah 24",
        "title": "The Holiness Code: 'You Shall Be Holy' and 'Love Your Neighbor as Yourself'",
        "book": "Leviticus", "c_start": 19, "v_start": 1, "c_end": 19, "v_end": 18,
        "linked_pericopes": ["lev-19-1-37-pericope"]
    },
    # Bamidbar Rabbah (Numbers)
    {
        "ref": "Bamidbar_Rabbah.16", "name": "Bamidbar Rabbah 16",
        "title": "The Mission of the Twelve Spies: Faith, Fear, and the Fruits of the Land",
        "book": "Numbers", "c_start": 13, "v_start": 1, "c_end": 13, "v_end": 33,
        "linked_pericopes": ["num-13-1-25-pericope", "num-13-26-33-pericope"]
    },
    {
        "ref": "Bamidbar_Rabbah.18", "name": "Bamidbar Rabbah 18",
        "title": "The Rebellion of Korah: Controversy Not for the Sake of Heaven",
        "book": "Numbers", "c_start": 16, "v_start": 1, "c_end": 16, "v_end": 35,
        "linked_pericopes": ["num-16-1-35-pericope"]
    },
    {
        "ref": "Bamidbar_Rabbah.19", "name": "Bamidbar Rabbah 19",
        "title": "The Bronze Serpent Lifted High: Directing Hearts to the Father in Heaven",
        "book": "Numbers", "c_start": 21, "v_start": 4, "c_end": 21, "v_end": 9,
        "linked_pericopes": ["num-21-4-9-pericope"]
    },
    {
        "ref": "Bamidbar_Rabbah.20", "name": "Bamidbar Rabbah 20",
        "title": "Balaam and his Talking Donkey: A Star Shall Step Forth Out of Jacob",
        "book": "Numbers", "c_start": 22, "v_start": 21, "c_end": 24, "v_end": 17,
        "linked_pericopes": ["num-22-21-41-pericope", "num-24-1-25-pericope"]
    },
    # Devarim Rabbah (Deuteronomy)
    {
        "ref": "Devarim_Rabbah.2", "name": "Devarim Rabbah 2",
        "title": "The Shema: 'Hear O Israel, the Lord Our God, the Lord is One' and Loving God with All Heart",
        "book": "Deuteronomy", "c_start": 6, "v_start": 4, "c_end": 6, "v_end": 9,
        "linked_pericopes": ["deut-6-1-19-pericope"]
    },
    {
        "ref": "Devarim_Rabbah.11", "name": "Devarim Rabbah 11",
        "title": "The Death of Moses on Mount Nebo: The Angel of Death and the Divine Kiss",
        "book": "Deuteronomy", "c_start": 34, "v_start": 1, "c_end": 34, "v_end": 12,
        "linked_pericopes": ["deut-34-1-12-pericope"]
    }
]

def fetch_torah_midrash() -> list[dict]:
    print("Fetching Midrash Rabbah for Exodus-Deuteronomy from Sefaria API...")
    items = []
    for info in SEFARIA_TORAH_MIDRASH:
        ref_id = info["ref"]
        url = f"https://www.sefaria.org/api/texts/{ref_id}?context=0"
        req = urllib.request.Request(url, headers={"User-Agent": "MTSBE-Corpus-Engine/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            print(f"Warning: Failed to fetch {ref_id}: {e}")
            continue

        en_texts = data.get("text", [])
        he_texts = data.get("he", [])

        # Flatten nested lists if any
        if en_texts and isinstance(en_texts[0], list):
            flat_en, flat_he = [], []
            for sub_en in en_texts:
                flat_en.extend(sub_en if isinstance(sub_en, list) else [sub_en])
            for sub_he in he_texts:
                flat_he.extend(sub_he if isinstance(sub_he, list) else [sub_he])
            en_texts = flat_en
            he_texts = flat_he

        # Group sections into chunks of ~3-5 sections
        chunk_size = 4
        for i in range(0, len(en_texts), chunk_size):
            slice_en = en_texts[i:i + chunk_size]
            slice_he = he_texts[i:i + chunk_size]

            en_combined = " ".join([clean_html(t) for t in slice_en if t and isinstance(t, str)]).strip()
            he_combined = " ".join([clean_html(t) for t in slice_he if t and isinstance(t, str)]).strip()

            if not en_combined or len(en_combined) < 150:
                continue

            sec_start = i + 1
            sec_end = min(i + chunk_size, len(en_texts))
            sec_range = f"{sec_start}–{sec_end}" if sec_start != sec_end else f"{sec_start}"

            cid = f"midrash-{ref_id.lower().replace('_', '-')}-{sec_start}-{sec_end}"
            items.append({
                "id": cid,
                "tradition": "midrash",
                "author": "Midrash Rabbah",
                "work": info["name"].split()[0] + " Rabbah",
                "reference": f"{info['name']}:{sec_range}",
                "book": info["book"],
                "chapter_start": info["c_start"],
                "verse_start": info["v_start"],
                "chapter_end": info["c_end"],
                "verse_end": info["v_end"],
                "title": f"{info['title']} ({info['name']}:{sec_range})",
                "text": en_combined,
                "original_language_text": he_combined,
                "linked_pericope_ids": info["linked_pericopes"],
                "metadata": {"source": "Sefaria REST API", "ref": f"{ref_id}:{sec_range}"}
            })

    print(f"Extracted {len(items)} Midrash commentary chunks for Torah.")
    return items

# =========================================================================
# 3. PHILO OF ALEXANDRIA: The Life of Moses (De Vita Mosis I & II)
# =========================================================================

PHILO_TREATISES = [
    {
        "id_suffix": "burning-bush",
        "title": "The Divine Vision at the Thorn Bush and the Secret of the Self-Existent Being",
        "book": "Exodus", "c_start": 3, "v_start": 1, "c_end": 4, "v_end": 17,
        "linked_pericopes": ["exod-3-1-22-pericope", "exod-4-1-17-pericope"],
        "source_book": 1,
        "search_pattern": r"There was a bush or briar.*?God"
    },
    {
        "id_suffix": "plagues-of-egypt",
        "title": "The Ten Plagues of Egypt as Cosmic Rebuke and the Discipline of Nature",
        "book": "Exodus", "c_start": 7, "v_start": 14, "c_end": 11, "v_end": 10,
        "linked_pericopes": ["exod-7-14-25-pericope", "exod-10-1-20-pericope"],
        "source_book": 1,
        "search_pattern": r"God made the natural elements.*?chastisement"
    },
    {
        "id_suffix": "parting-red-sea",
        "title": "The Parting of the Red Sea: The Pillar of Cloud and Triumph of Virtue",
        "book": "Exodus", "c_start": 14, "v_start": 15, "c_end": 15, "v_end": 21,
        "linked_pericopes": ["exod-14-1-31-pericope", "exod-15-1-21-pericope"],
        "source_book": 1,
        "search_pattern": r"the sea was cut into two parts.*?chariots"
    },
    {
        "id_suffix": "divine-cloud-sinai",
        "title": "Entering the Divine Cloud of Mount Sinai and the Archetype of the Heavenly Tabernacle",
        "book": "Exodus", "c_start": 19, "v_start": 16, "c_end": 25, "v_end": 40,
        "linked_pericopes": ["exod-19-1-25-pericope", "exod-25-1-40-pericope"],
        "source_book": 2,
        "search_pattern": r"Moses entered into the darkness where God was.*?pattern"
    },
    {
        "id_suffix": "decalogue-law",
        "title": "The Decalogue and the Priesthood: The Ten Words as Universal Cosmic Logos",
        "book": "Exodus", "c_start": 20, "v_start": 1, "c_end": 20, "v_end": 17,
        "linked_pericopes": ["exod-20-1-21-pericope"],
        "source_book": 2,
        "search_pattern": r"The ten commandments.*?virtue"
    },
    {
        "id_suffix": "passing-of-moses",
        "title": "The Sacred Passing and Prophet's Translation: Recording his Own Death in Divine Scripture",
        "book": "Deuteronomy", "c_start": 34, "v_start": 1, "c_end": 34, "v_end": 12,
        "linked_pericopes": ["deut-34-1-12-pericope"],
        "source_book": 2,
        "search_pattern": r"When he was now about to depart from mankind.*?prophecy"
    }
]

def fetch_philo_commentaries() -> list[dict]:
    print("Fetching Philo of Alexandria (Life of Moses I & II)...")
    req1 = urllib.request.Request("https://www.earlychristianwritings.com/yonge/book24.html", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req1) as r:
        text1 = clean_html(r.read().decode("utf-8", errors="ignore"))

    req2 = urllib.request.Request("https://www.earlychristianwritings.com/yonge/book25.html", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req2) as r:
        text2 = clean_html(r.read().decode("utf-8", errors="ignore"))

    items = []
    
    # Section 1: Burning Bush (from Book 1)
    pos1 = text1.find("There was a bush or briar")
    if pos1 != -1:
        chunk1 = text1[pos1 : pos1 + 2800]
        items.append({
            "id": "philo-moses-1-burning-bush",
            "tradition": "patristic",
            "author": "Philo of Alexandria",
            "work": "The Life of Moses",
            "reference": "De Vita Mosis I.12",
            "book": "Exodus", "c_start": 3, "v_start": 1, "c_end": 3, "v_end": 14,
            "title": "The Vision at the Burning Thorn Bush: The Fire That Consumes Not and the Being That Is",
            "text": chunk1,
            "original_language_text": None,
            "linked_pericope_ids": ["exod-3-1-22-pericope"],
            "metadata": {"source": "Philo of Alexandria, Yonge Translation", "work": "De Vita Mosis I.12"}
        })

    # Section 2: Plagues of Egypt
    pos2 = text1.find("He attacked them first with water")
    if pos2 != -1:
        chunk2 = text1[pos2 : pos2 + 2800]
        items.append({
            "id": "philo-moses-1-plagues",
            "tradition": "patristic",
            "author": "Philo of Alexandria",
            "work": "The Life of Moses",
            "reference": "De Vita Mosis I.17–20",
            "book": "Exodus", "c_start": 7, "v_start": 14, "c_end": 10, "v_end": 20,
            "title": "The Plagues of Egypt: Cosmic Elements Marshaled Against the Obstinacy of Tyranny",
            "text": chunk2,
            "original_language_text": None,
            "linked_pericope_ids": ["exod-7-14-25-pericope", "exod-10-1-20-pericope"],
            "metadata": {"source": "Philo of Alexandria, Yonge Translation", "work": "De Vita Mosis I.17"}
        })

    # Section 3: Crossing of Red Sea
    pos3 = text1.find("And when the people saw themselves thus enclosed")
    if pos3 != -1:
        chunk3 = text1[pos3 : pos3 + 2800]
        items.append({
            "id": "philo-moses-1-red-sea",
            "tradition": "patristic",
            "author": "Philo of Alexandria",
            "work": "The Life of Moses",
            "reference": "De Vita Mosis I.29–32",
            "book": "Exodus", "c_start": 14, "v_start": 1, "c_end": 15, "v_end": 21,
            "title": "The Parting of the Red Sea and Song of Triumph Over Bodily Passions",
            "text": chunk3,
            "original_language_text": None,
            "linked_pericope_ids": ["exod-14-1-31-pericope", "exod-15-1-21-pericope"],
            "metadata": {"source": "Philo of Alexandria, Yonge Translation", "work": "De Vita Mosis I.29"}
        })

    # Section 4: Heavenly Tabernacle (from Book 2)
    pos4 = text2.find("He was therefore summoned to the highest peak of Mount Sinai")
    if pos4 != -1:
        chunk4 = text2[pos4 : pos4 + 2800]
        items.append({
            "id": "philo-moses-2-tabernacle-archetype",
            "tradition": "patristic",
            "author": "Philo of Alexandria",
            "work": "The Life of Moses",
            "reference": "De Vita Mosis II.14–16",
            "book": "Exodus", "c_start": 25, "v_start": 1, "c_end": 26, "v_end": 37,
            "title": "Mount Sinai and the Heavenly Archetype: Contemplating the Pattern of the Tabernacle",
            "text": chunk4,
            "original_language_text": None,
            "linked_pericope_ids": ["exod-19-1-25-pericope", "exod-25-1-40-pericope"],
            "metadata": {"source": "Philo of Alexandria, Yonge Translation", "work": "De Vita Mosis II.14"}
        })

    # Section 5: The Passing of Moses (from Book 2)
    pos5 = text2.find("When he was now on the point of departing from mankind")
    if pos5 != -1:
        chunk5 = text2[pos5 : pos5 + 2800]
        items.append({
            "id": "philo-moses-2-death-of-moses",
            "tradition": "patristic",
            "author": "Philo of Alexandria",
            "work": "The Life of Moses",
            "reference": "De Vita Mosis II.51",
            "book": "Deuteronomy", "c_start": 34, "v_start": 1, "c_end": 34, "v_end": 12,
            "title": "The Prophet's Translation: Recording his Own Death in Divine Scripture Prior to Departure",
            "text": chunk5,
            "original_language_text": None,
            "linked_pericope_ids": ["deut-34-1-12-pericope"],
            "metadata": {"source": "Philo of Alexandria, Yonge Translation", "work": "De Vita Mosis II.51"}
        })

    print(f"Extracted {len(items)} Philo commentary treatises.")
    return items

# =========================================================================
# EMBEDDING & UPSERT PIPELINE
# =========================================================================

def generate_embeddings(items: list[dict]) -> list[dict]:
    print(f"Initializing Vertex AI Client to embed {len(items)} commentary items...")
    client = genai.Client(vertexai=True, project="mtsbe-1208613", location="us")

    total = len(items)
    for i, it in enumerate(items):
        embed_content = f"{it['tradition'].upper()} Commentary by {it['author']} on {it['work']} ({it['reference']}): {it['title']}\n\n{it['text'][:2000]}"
        if i % 10 == 0 or i == total - 1:
            print(f"Embedding {i + 1}/{total}: [{it['tradition'].upper()}] {it['author']} - {it['reference']}...")

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
                it["embedding"] = res.embeddings[0].values
                break
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for {it['id']}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(3 * (attempt + 1))
                else:
                    raise

        time.sleep(0.04)

    print(f"Successfully generated embeddings for all {total} commentary items.")
    return items

def upsert_commentaries(conn, items: list[dict]):
    cur = conn.cursor()
    print(f"Upserting {len(items)} commentary chunks into Cloud SQL 'commentaries' table...")

    query = """
        INSERT INTO commentaries (
            id, tradition, author, work, reference,
            book, chapter_start, verse_start, chapter_end, verse_end,
            title, text, original_language_text, linked_pericope_ids,
            metadata, embedding
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s
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

    records = [
        (
            it["id"], it["tradition"], it["author"], it["work"], it["reference"],
            it.get("book"), it.get("chapter_start"), it.get("verse_start"), it.get("chapter_end"), it.get("verse_end"),
            it["title"], it["text"], it.get("original_language_text"), it.get("linked_pericope_ids", []),
            json.dumps(it.get("metadata", {})), it["embedding"]
        )
        for it in items
    ]

    cur.executemany(query, records)
    conn.commit()
    cur.close()
    print(f"Successfully upserted {len(items)} commentaries into Cloud SQL.")

def main():
    print("==================================================")
    print("=== MTSBE Multi-Tradition Torah Commentary Ingestion ===")
    print("==================================================")

    # 1. Fetch Josephus Books 2, 3, 4
    josephus_items = fetch_josephus_torah_commentaries()

    # 2. Fetch Midrash Rabbah for Exodus-Deut
    midrash_items = fetch_torah_midrash()

    # 3. Fetch Philo treatises
    philo_items = fetch_philo_commentaries()

    all_items = josephus_items + midrash_items + philo_items
    print(f"\nTotal Torah commentaries extracted: {len(all_items)} chunks.")
    print(f"  • Josephus (Historical): {len(josephus_items)}")
    print(f"  • Midrash Rabbah (Midrash): {len(midrash_items)}")
    print(f"  • Philo of Alexandria (Patristic): {len(philo_items)}")

    # 4. Generate embeddings
    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)
    cache_path = os.path.join(PROCESSED_DATA_DIR, "torah_commentaries_embedded.json")

    if os.path.exists(cache_path):
        print(f"Loading cached embedded commentaries from {cache_path}...")
        with open(cache_path, "r", encoding="utf-8") as f:
            all_items = json.load(f)
    else:
        all_items = generate_embeddings(all_items)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(all_items, f, indent=2, ensure_ascii=False)
        print(f"Saved embedded commentaries to {cache_path}.")

    # 5. Upsert to Cloud SQL
    conn = get_db_connection()
    upsert_commentaries(conn, all_items)

    # 6. Verify total commentaries in database
    cur = conn.cursor()
    cur.execute("SELECT tradition, count(*) FROM commentaries GROUP BY tradition ORDER BY tradition;")
    print("\nDatabase Commentaries Summary:")
    for t, c in cur.fetchall():
        print(f"  • {t.upper()}: {c} records")

    cur.close()
    conn.close()
    print("\n=== Multi-Tradition Torah Commentaries Successfully Ingested ===")

if __name__ == "__main__":
    main()
