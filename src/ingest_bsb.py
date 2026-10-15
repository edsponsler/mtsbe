import os
import json
import psycopg2
import urllib.request

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "mtsbe_data")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "ChangeThisStrongPassword123!")

BSB_JSON_URL = "https://raw.githubusercontent.com/amir-hanna/bible/master/bsb.json"

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def ensure_columns_exist(conn):
    cur = conn.cursor()
    # Add english_text to pericopes if it doesn't exist
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='pericopes' and column_name='english_text';
    """)
    if not cur.fetchone():
        print("Adding 'english_text' column to pericopes...")
        cur.execute("ALTER TABLE pericopes ADD COLUMN english_text TEXT;")
    
    # Add english_text to verses if it doesn't exist
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='verses' and column_name='english_text';
    """)
    if not cur.fetchone():
        print("Adding 'english_text' column to verses...")
        cur.execute("ALTER TABLE verses ADD COLUMN english_text TEXT;")
    
    conn.commit()
    cur.close()

def load_bsb_json():
    print(f"Downloading BSB JSON from {BSB_JSON_URL}...")
    req = urllib.request.Request(BSB_JSON_URL, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
    return data['_default']

def build_book_map(bsb_data):
    # Map (book, chapter, verse) to text
    book_map = {}
    for key, item in bsb_data.items():
        b = item['book']
        c = int(item['chapter'])
        v = int(item['verse'])
        t = item['text']
        
        if b not in book_map:
            book_map[b] = {}
        if c not in book_map[b]:
            book_map[b][c] = {}
        book_map[b][c][v] = t
    return book_map

def main():
    conn = get_db_connection()
    ensure_columns_exist(conn)
    
    bsb_data = load_bsb_json()
    book_map = build_book_map(bsb_data)
    
    cur = conn.cursor()
    print("Fetching pericopes...")
    cur.execute("SELECT id, book, chapter_start, verse_start, chapter_end, verse_end FROM pericopes")
    pericopes = cur.fetchall()
    
    updated_count = 0
    missing_verses = []

    book_mapping = {
        "Gen": "Genesis"
    }

    for p_id, book, c_start, v_start, c_end, v_end in pericopes:
        # We need to gather verses between (c_start, v_start) and (c_end, v_end)
        # Note: assuming book names match exactly (e.g., 'Genesis')
        english_text_parts = []
        
        json_book = book_mapping.get(book, book)

        if json_book not in book_map:
            print(f"Warning: Book {json_book} (from {book}) not found in BSB data.")
            continue
            
        c = c_start
        v = v_start
        
        while (c < c_end) or (c == c_end and v <= v_end):
            # Check if verse exists
            if c in book_map[json_book] and v in book_map[json_book][c]:
                english_text_parts.append(f"[{c}:{v}] {book_map[json_book][c][v]}")
                v += 1
            else:
                # Verse doesn't exist, might be end of chapter
                # Let's check if there are more verses in this chapter
                if c in book_map[json_book] and any(vk > v for vk in book_map[json_book][c].keys()):
                    # missing verse in middle of chapter?
                    v += 1
                else:
                    # Move to next chapter
                    c += 1
                    v = 1
                    if c > c_end:
                        break

        if english_text_parts:
            english_text = " ".join(english_text_parts)
            cur.execute("UPDATE pericopes SET english_text = %s WHERE id = %s", (english_text, p_id))
            updated_count += 1
        else:
            missing_verses.append(p_id)
            
    conn.commit()
    print(f"Updated {updated_count} pericopes with English text.")
    if missing_verses:
        print(f"Could not find english text for {len(missing_verses)} pericopes.")
        
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
