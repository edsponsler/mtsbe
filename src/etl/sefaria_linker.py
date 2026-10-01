import json
import os
import re

def convert_ref_to_osis_id(ref):
    """
    Converts a Sefaria reference like 'Genesis 2:1' to our OSIS-style chunk ID 'gen-2-1'.
    Returns None if it's not a Genesis biblical reference.
    """
    match = re.match(r'^Genesis\s+(\d+):(\d+)$', ref)
    if match:
        chapter, verse = match.groups()
        return f"gen-{chapter}-{verse}"
    return None

def link_midrash_to_chunks(chunks_file, links_file, output_file):
    print(f"Loading chunks from {chunks_file}...")
    with open(chunks_file, 'r', encoding='utf-8') as f:
        chunks = json.load(f)
        
    print(f"Loading Sefaria links from {links_file}...")
    with open(links_file, 'r', encoding='utf-8') as f:
        links = json.load(f)
        
    # Build a lookup dictionary for verses and pericopes
    chunk_dict = {chunk['id']: chunk for chunk in chunks}
    
    # Track how many links we successfully map
    mapped_links = 0
    
    print("Processing links...")
    for link in links:
        # We only care about midrash links for this PoC right now
        if link.get("type") == "midrash":
            refs = link.get("refs", [])
            if len(refs) != 2:
                continue
                
            # One ref is the Bible verse, the other is the Midrash
            # We don't know which is which in the array, so we test both
            verse_ref = None
            midrash_ref = None
            
            for ref in refs:
                if ref.startswith("Genesis "):
                    # Let's verify it's a verse and not 'Genesis Rabbah'
                    if not ref.startswith("Genesis Rabbah"):
                        verse_ref = ref
                else:
                    midrash_ref = ref
                    
            if not midrash_ref and "Genesis Rabbah" in refs[0]:
                 midrash_ref = refs[0]
            elif not midrash_ref and "Genesis Rabbah" in refs[1]:
                 midrash_ref = refs[1]

            
            if verse_ref and midrash_ref:
                verse_id = convert_ref_to_osis_id(verse_ref)
                if verse_id and verse_id in chunk_dict:
                    # Update the verse chunk's external links (if we added external_links to verses)
                    # Wait, our schema puts external_links on the PERICOPE (parent chunk), not the verse directly!
                    # Let's find the parent pericope for this verse.
                    verse_chunk = chunk_dict[verse_id]
                    parent_id = verse_chunk.get("parent_pericope_id")
                    
                    if parent_id and parent_id in chunk_dict:
                        parent_chunk = chunk_dict[parent_id]
                        if midrash_ref not in parent_chunk["external_links"]["midrash"]:
                            parent_chunk["external_links"]["midrash"].append(midrash_ref)
                            mapped_links += 1

    print(f"Successfully mapped {mapped_links} Midrash references to Pericopes.")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(list(chunk_dict.values()), f, indent=2)
        
    print(f"Saved linked chunks to {output_file}")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    chunks_file = os.path.join(script_dir, "../../data/processed/genesis_full.json")
    links_file = os.path.join(script_dir, "../../data/raw/sefaria_links_sample.json")
    output_file = os.path.join(script_dir, "../../data/processed/genesis_linked.json")
    
    link_midrash_to_chunks(chunks_file, links_file, output_file)
