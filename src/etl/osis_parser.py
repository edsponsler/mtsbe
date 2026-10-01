import xml.etree.ElementTree as ET
import json
import os

def parse_osis_to_chunks(xml_path):
    """
    Parses an OSIS XML file into the 3-tier MTSBE hierarchical chunking schema.
    Extracts: Book -> Chapter -> Pericope (Section) -> Verse.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    # Strip namespaces for easier parsing in this PoC
    for elem in root.iter():
        if '}' in elem.tag:
            elem.tag = elem.tag.split('}', 1)[1]
            
    chunks = []
    
    # 1. Find the Book
    for book in root.findall('.//div[@type="book"]'):
        book_id = book.get('osisID')
        book_title = book.find('title').text if book.find('title') is not None else book_id
        
        # 2. Find Chapters
        for chapter in book.findall('.//chapter'):
            chapter_id = chapter.get('osisID') # e.g., Gen.22
            chapter_num = chapter_id.split('.')[1] if '.' in chapter_id else "1"
            
            # 3. Find Pericopes (usually encoded as 'section' div in OSIS)
            sections = chapter.findall('.//div[@type="section"]')
            if not sections:
                # Fallback: Treat the entire chapter as a single pericope if no section markup exists
                sections = [chapter]
                
            for section in sections:
                pericope_title_elem = section.find('title')
                pericope_title = pericope_title_elem.text if pericope_title_elem is not None else f"{book_title} Chapter {chapter_num}"
                
                verses = []
                verse_ids = []
                
                # 4. Find Verses within the Section
                for verse in section.findall('.//verse'):
                    v_id = verse.get('osisID') # e.g., Gen.22.1
                    if v_id is None:
                        continue
                    v_text = "".join(verse.itertext()).strip()
                    verses.append({
                        "id": v_id.lower().replace('.', '-'),
                        "text": v_text
                    })
                    verse_ids.append(v_id.lower().replace('.', '-'))
                
                if verses:
                    pericope_text = " ".join([v["text"] for v in verses])
                    
                    # Calculate verse start and end for metadata
                    v_start = int(verses[0]['id'].split('-')[-1])
                    v_end = int(verses[-1]['id'].split('-')[-1])
                    
                    # e.g., gen-22-1-2-pericope
                    pericope_id = f"{book_id.lower()}-{chapter_num}-{v_start}-{v_end}-pericope"
                    
                    # --- Create Parent Chunk (Pericope) ---
                    parent_chunk = {
                        "id": pericope_id,
                        "type": "pericope",
                        "corpus": "biblical",
                        "book": book_title,
                        "chapter_start": int(chapter_num),
                        "verse_start": v_start,
                        "chapter_end": int(chapter_num),
                        "verse_end": v_end,
                        "pericope_title": pericope_title,
                        "text": pericope_text,
                        "child_verse_ids": verse_ids,
                        "external_links": {
                            "midrash": [],
                            "church_fathers": [],
                            "secular": []
                        }
                    }
                    chunks.append(parent_chunk)
                    
                    # --- Create Child Chunks (Verses) ---
                    for v in verses:
                        child_chunk = {
                            "id": v["id"],
                            "type": "verse",
                            "corpus": "biblical",
                            "book": book_title,
                            "chapter": int(chapter_num),
                            "verse": int(v["id"].split('-')[-1]),
                            "text": v["text"],
                            "parent_pericope_id": pericope_id
                        }
                        chunks.append(child_chunk)
                        
    return chunks

import sys

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else os.path.join(script_dir, "../../data/processed/output.json")
    else:
        input_file = os.path.join(script_dir, "../../data/raw/genesis_sample.xml")
        output_file = os.path.join(script_dir, "../../data/processed/genesis_chunks.json")
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    print(f"Parsing OSIS XML from: {input_file}...")
    chunks = parse_osis_to_chunks(input_file)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, indent=2)
        
    parent_count = sum(1 for c in chunks if c["type"] == "pericope")
    verse_count = len(chunks) - parent_count
    print(f"Successfully processed {len(chunks)} chunks ({parent_count} Pericopes + {verse_count} Verses).")
    print(f"Saved cleanly structured JSON to: {output_file}")
