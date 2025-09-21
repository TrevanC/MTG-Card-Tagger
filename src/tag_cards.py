#!/usr/bin/env python3
"""
tag_cards.py — MTG EDH card tagger (v0.4.3 schema)
- Supports sequential mode, asyncio parallel mode, and batch-prompting (multi-card per request).
- Reads taxonomy.slim.yaml and card_tag.slim.schema.json to ground the model.
- Writes results to JSONL.
"""

import argparse, asyncio, json, os, random, sys, time
from pathlib import Path
from typing import Dict, List, Any, Tuple
from tqdm import tqdm

try:
    from openai import OpenAI, AsyncOpenAI
except ImportError:
    print("Please install openai: pip install openai")
    sys.exit(1)

DEFAULT_MODEL = "gpt-4o-mini"
SYSTEM_ROLE = "You are an expert in Magic: The Gathering EDH deckbuilding. Tag cards according to the provided taxonomy and schema. Output strictly valid JSON."

def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def load_grounding(taxonomy_path: Path, schema_path: Path) -> Tuple[str, str]:
    return read_file(taxonomy_path), read_file(schema_path)

def make_system_prompt(taxonomy_text: str, schema_text: str) -> str:
    return f"""{SYSTEM_ROLE}

TAXONOMY (YAML):
{taxonomy_text}

SCHEMA (JSON):
{schema_text}

Rules:
- Follow enums and limits exactly.
- Use only allowed values.
- Output JSON ONLY.
"""

def clean_json(txt: str) -> str:
    txt = txt.strip()
    try:
        json.loads(txt)
        return txt
    except Exception:
        pass
    first = min([i for i in [txt.find("{"), txt.find("[")] if i != -1], default=-1)
    if first == -1: 
        return txt
    for end in range(len(txt), first, -1):
        snippet = txt[first:end]
        try:
            json.loads(snippet); return snippet
        except Exception: 
            continue
    return txt

def backoff(attempt: int):
    time.sleep(min((1.5 ** attempt) + random.random()*0.2, 30))

def get_output_filename(base_path: Path, file_index: int) -> Path:
    """Generate output filename with index for file splitting"""
    if file_index == 0:
        return base_path
    else:
        stem = base_path.stem
        suffix = base_path.suffix
        return base_path.parent / f"{stem}_part{file_index + 1}{suffix}"

# ---------- Sequential ----------
def tag_card_sync(client, system_prompt: str, model: str, card: Dict[str, Any], retries=5):
    user_prompt = f"""Card:
Name: {card.get('name')}
Oracle ID: {card.get('oracle_id')}
Oracle Text: {card.get('oracle_text')}

Tag this card strictly according to the schema. Output JSON only.
"""
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role":"system","content":system_prompt},
                          {"role":"user","content":user_prompt}],
                # temperature=0,
            )
            content = clean_json(resp.choices[0].message.content)
            return json.loads(content)
        except Exception as e:
            sys.stderr.write(f"[warn] retry {attempt+1} for {card['name']}: {e}\n")
            backoff(attempt)
    return None

# ---------- Batch Prompting ----------
def tag_cards_batch_sync(client, system_prompt: str, model: str, cards: List[Dict[str,Any]], retries=5):
    lines = [f"- name: {c['name']}\n  oracle_id: {c['oracle_id']}\n  oracle_text: {c['oracle_text']}" for c in cards]
    user_prompt = f"""Cards (return JSON array in order):
{chr(10).join(lines)}"""
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role":"system","content":system_prompt},
                          {"role":"user","content":user_prompt}],
                # temperature=0,
            )
            arr = json.loads(clean_json(resp.choices[0].message.content))
            return arr if isinstance(arr,list) else arr.get("results",[])
        except Exception as e:
            sys.stderr.write(f"[warn] batch retry {attempt+1}: {e}\n")
            backoff(attempt)
    return [None]*len(cards)

# ---------- Async ----------
async def tag_card_async(client, system_prompt, model, card, retries=5):
    user_prompt = f"""Card:
Name: {card['name']}
Oracle ID: {card['oracle_id']}
Oracle Text: {card['oracle_text']}

Tag this card strictly according to the schema. Output JSON only.
"""
    for attempt in range(retries):
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role":"system","content":system_prompt},
                          {"role":"user","content":user_prompt}],
                # temperature=0,
            )
            content = clean_json(resp.choices[0].message.content)
            return json.loads(content)
        except Exception as e:
            sys.stderr.write(f"[warn] async retry {attempt+1} for {card['name']}: {e}\n")
            await asyncio.sleep(min((1.5 ** attempt) + random.random()*0.2, 30))
    return None

async def batch_tag_cards_async(cards: List[Dict[str,Any]], taxonomy: Path, schema: Path,
                                output_path: Path, model: str, concurrency: int, split_size: int = 0):
    taxonomy_text, schema_text = load_grounding(taxonomy, schema)
    system_prompt = make_system_prompt(taxonomy_text, schema_text)
    client = AsyncOpenAI()

    sem = asyncio.Semaphore(concurrency)
    results = []
    successful_count = 0
    current_file_index = 0
    current_file_count = 0

    # Create progress bar
    pbar = tqdm(total=len(cards), desc="Processing cards", unit="card")

    async def safe_tag(card):
        nonlocal successful_count, current_file_index, current_file_count
        async with sem:
            result = await tag_card_async(client, system_prompt, model, card)
            if result:
                # Check if we need to switch to a new file
                if split_size > 0 and current_file_count >= split_size:
                    current_file_index += 1
                    current_file_count = 0
                    tqdm.write(f"Switching to new file: {get_output_filename(output_path, current_file_index)}")
                
                # Write result to current file
                current_output_path = get_output_filename(output_path, current_file_index)
                with current_output_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(result) + "\n")
                
                successful_count += 1
                current_file_count += 1
            
            # Update progress bar
            pbar.update(1)
            pbar.set_postfix({"Successful": successful_count})
            return result

    tasks = [safe_tag(card) for card in cards]
    results = await asyncio.gather(*tasks)
    
    pbar.close()
    print(f"Completed processing {len(results)} cards, {successful_count} successful")
    if split_size > 0:
        print(f"Created {current_file_index + 1} output files")

# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="../data/scryfall_oracle.json", help="Input JSON file of cards")
    ap.add_argument("--output", default="../output/tagged_cards.jsonl", help="Output JSONL file")
    ap.add_argument("--taxonomy", default="taxonomy.slim.yaml")
    ap.add_argument("--schema", default="card_tag.slim.schema.json")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--async", dest="use_async", action="store_true", help="Use async parallel mode")
    ap.add_argument("--concurrency", type=int, default=10)
    ap.add_argument("--batch-size", type=int, default=0, help="Cards per batch (0 = disabled)")
    ap.add_argument("--edh-only", action="store_true", help="Only process EDH/Commander legal cards")
    ap.add_argument("--colors", nargs="*", choices=['W', 'U', 'B', 'R', 'G'], 
                   help="Filter by color identity (e.g., --colors W U for Azorius)")
    ap.add_argument("--colorless", action="store_true", help="Include colorless cards (no color identity)")
    ap.add_argument("--resume", action="store_true", help="Resume from existing output file (skip already processed cards)")
    ap.add_argument("--split-size", type=int, default=0, help="Create new file every N cards (0 = disabled)")
    args = ap.parse_args()

    input_cards = json.loads(Path(args.input).read_text(encoding="utf-8"))
    taxonomy_text, schema_text = load_grounding(Path(args.taxonomy), Path(args.schema))
    system_prompt = make_system_prompt(taxonomy_text, schema_text)
    
    # Ensure output directory exists
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    
    # Apply filters
    original_count = len(input_cards)
    
    # Filter cards to only include those with oracle_text (some cards might not have oracle text)
    input_cards = [card for card in input_cards if card.get('oracle_text')]
    print(f"Cards with oracle text: {len(input_cards)} (from {original_count} total)")
    
    # Filter for EDH legality if requested
    if args.edh_only:
        edh_legal = [card for card in input_cards 
                    if card.get('legalities', {}).get('commander') == 'legal']
        print(f"EDH-legal cards: {len(edh_legal)} (from {len(input_cards)} with oracle text)")
        input_cards = edh_legal
    
    # Filter by color identity if requested
    if args.colors or args.colorless:
        target_colors = set(args.colors) if args.colors else set()
        color_filtered = []
        
        for card in input_cards:
            card_colors = set(card.get('color_identity', []))
            
            # Check if card matches color filter
            if args.colorless and not card_colors:
                # Include colorless cards
                color_filtered.append(card)
            elif target_colors and card_colors == target_colors:
                # Include cards that exactly match the specified colors
                color_filtered.append(card)
        
        if args.colors:
            color_str = ' '.join(sorted(args.colors))
            print(f"Cards with color identity {color_str}: {len(color_filtered)}")
        if args.colorless:
            colorless_count = len([c for c in color_filtered if not c.get('color_identity')])
            print(f"Colorless cards: {colorless_count}")
        
        input_cards = color_filtered
    
    # Handle resume functionality
    if args.resume and Path(args.output).exists():
        # Read existing results to skip already processed cards
        processed_oracle_ids = set()
        try:
            with open(args.output, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        result = json.loads(line.strip())
                        processed_oracle_ids.add(result.get("oracle_id"))
            print(f"Found {len(processed_oracle_ids)} already processed cards")
            # Filter out already processed cards
            input_cards = [card for card in input_cards 
                          if card.get("oracle_id") not in processed_oracle_ids]
            print(f"Remaining cards to process: {len(input_cards)}")
        except Exception as e:
            print(f"Warning: Could not read existing output file: {e}")
    elif not args.resume:
        # Clear output file if not resuming
        Path(args.output).write_text("", encoding="utf-8")
        print(f"Cleared output file: {args.output}")
    
    print(f"Final processing count: {len(input_cards)} cards")

    if args.use_async:
        asyncio.run(batch_tag_cards_async(input_cards, Path(args.taxonomy), Path(args.schema),
                                          Path(args.output), args.model, args.concurrency, args.split_size))
    elif args.batch_size > 0:
        client = OpenAI()
        successful_count = 0
        current_file_index = 0
        current_file_count = 0
        
        # Create progress bar for batches
        num_batches = (len(input_cards) + args.batch_size - 1) // args.batch_size
        pbar = tqdm(total=num_batches, desc="Processing batches", unit="batch")
        
        for i in range(0, len(input_cards), args.batch_size):
            batch = input_cards[i:i+args.batch_size]
            tagged_batch = tag_cards_batch_sync(client, system_prompt, args.model, batch)
            
            # Check if we need to switch to a new file
            if args.split_size > 0 and current_file_count >= args.split_size:
                current_file_index += 1
                current_file_count = 0
                tqdm.write(f"Switching to new file: {get_output_filename(Path(args.output), current_file_index)}")
            
            # Write results to current file
            current_output_path = get_output_filename(Path(args.output), current_file_index)
            with current_output_path.open("a", encoding="utf-8") as f:
                for r in tagged_batch:
                    if r:
                        f.write(json.dumps(r) + "\n")
                        successful_count += 1
                        current_file_count += 1
            
            # Update progress bar
            pbar.update(1)
            pbar.set_postfix({"Cards": successful_count})
        
        pbar.close()
        print(f"Completed processing {len(input_cards)} cards in batches of {args.batch_size}, {successful_count} successful")
        if args.split_size > 0:
            print(f"Created {current_file_index + 1} output files")
    else:
        client = OpenAI()
        successful_count = 0
        current_file_index = 0
        current_file_count = 0
        
        # Create progress bar for sequential processing
        pbar = tqdm(total=len(input_cards), desc="Processing cards", unit="card")
        
        for i, card in enumerate(input_cards):
            tagged = tag_card_sync(client, system_prompt, args.model, card)
            if tagged:
                # Check if we need to switch to a new file
                if args.split_size > 0 and current_file_count >= args.split_size:
                    current_file_index += 1
                    current_file_count = 0
                    tqdm.write(f"Switching to new file: {get_output_filename(Path(args.output), current_file_index)}")
                
                # Write result to current file
                current_output_path = get_output_filename(Path(args.output), current_file_index)
                with current_output_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(tagged) + "\n")
                
                successful_count += 1
                current_file_count += 1
            
            # Update progress bar
            pbar.update(1)
            pbar.set_postfix({"Successful": successful_count})
        
        pbar.close()
        print(f"Completed processing {len(input_cards)} cards sequentially, {successful_count} successful")
        if args.split_size > 0:
            print(f"Created {current_file_index + 1} output files")

if __name__ == "__main__":
    main()
