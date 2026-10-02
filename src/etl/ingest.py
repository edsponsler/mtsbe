import json
import os
import psycopg2
from pgvector.psycopg2 import register_vector

def load_data(file_path: str):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def ingest_data(data, conn):
    # Register pgvector type
    register_vector(conn)
    
    cur = conn.cursor()
    
    pericopes = []
    verses = []
    
    for item in data:
        if item.get("type") == "pericope":
            pericopes.append((
                item["id"], item.get("type", "pericope"), item.get("corpus"), item.get("book"),
                item.get("chapter_start"), item.get("verse_start"), item.get("chapter_end"), item.get("verse_end"),
                item.get("pericope_title"), item.get("text"), item.get("child_verse_ids", []),
                json.dumps(item.get("external_links", {})), item.get("embedding")
            ))
        elif item.get("type") == "verse":
            verses.append((
                item["id"], item.get("type", "verse"), item.get("corpus"), item.get("book"),
                item.get("chapter"), item.get("verse"), item.get("text"), item.get("parent_pericope_id"),
                item.get("embedding")
            ))
            
    # Insert pericopes
    if pericopes:
        print(f"Inserting {len(pericopes)} pericopes...")
        pericope_query = """
            INSERT INTO pericopes (id, type, corpus, book, chapter_start, verse_start, chapter_end, verse_end, pericope_title, text, child_verse_ids, external_links, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                type = EXCLUDED.type, corpus = EXCLUDED.corpus, book = EXCLUDED.book,
                chapter_start = EXCLUDED.chapter_start, verse_start = EXCLUDED.verse_start,
                chapter_end = EXCLUDED.chapter_end, verse_end = EXCLUDED.verse_end,
                pericope_title = EXCLUDED.pericope_title, text = EXCLUDED.text,
                child_verse_ids = EXCLUDED.child_verse_ids, external_links = EXCLUDED.external_links,
                embedding = EXCLUDED.embedding
        """
        cur.executemany(pericope_query, pericopes)
    
    # Insert verses
    if verses:
        print(f"Inserting {len(verses)} verses...")
        verse_query = """
            INSERT INTO verses (id, type, corpus, book, chapter, verse, text, parent_pericope_id, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                type = EXCLUDED.type, corpus = EXCLUDED.corpus, book = EXCLUDED.book,
                chapter = EXCLUDED.chapter, verse = EXCLUDED.verse, text = EXCLUDED.text,
                parent_pericope_id = EXCLUDED.parent_pericope_id, embedding = EXCLUDED.embedding
        """
        cur.executemany(verse_query, verses)
    
    conn.commit()
    cur.close()

def main():
    input_file = "data/processed/genesis_embedded.json"
    if not os.path.exists(input_file):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        input_file = os.path.join(script_dir, "../../data/processed/genesis_embedded.json")
        
    # DB connection parameters
    # The default setup suggests a Cloud SQL Auth Proxy is running on localhost
    DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
    DB_PORT = os.environ.get("DB_PORT", "5432")
    DB_NAME = os.environ.get("DB_NAME", "mtsbe_data")
    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "ChangeThisStrongPassword123!")
    
    print("Connecting to database...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
    except Exception as e:
        print(f"Error connecting to DB: {e}")
        print("Note: To connect to Cloud SQL locally, ensure you are running the Cloud SQL Auth Proxy:")
        print("      ./cloud-sql-proxy mtsbe-1208613:us-central1:mtsbe-db")
        return
        
    print(f"Loading data from {input_file}...")
    if not os.path.exists(input_file):
        print(f"Input file not found: {input_file}")
        print("Please run embedder.py first to generate the embeddings.")
        return
        
    data = load_data(input_file)
    
    print("Ingesting data into database...")
    ingest_data(data, conn)
    
    conn.close()
    print("Ingestion complete!")

if __name__ == "__main__":
    main()
