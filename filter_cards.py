#!/usr/bin/env python3
"""
Filter scryfall_oracle.json for EDH-legal cards in Black, White, Red, and their combinations.
Creates a new JSON file with only the filtered cards.
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Set

def get_color_combinations() -> List[Set[str]]:
    """Get all valid color combinations for B, W, R"""
    colors = ['B', 'W', 'R']
    combinations = []
    
    # Single colors
    for color in colors:
        combinations.append({color})
    
    # Two-color combinations
    for i in range(len(colors)):
        for j in range(i + 1, len(colors)):
            combinations.append({colors[i], colors[j]})
    
    # Three-color combination
    combinations.append({'B', 'W', 'R'})
    
    return combinations

def filter_cards(input_file: Path, output_file: Path) -> None:
    """Filter cards based on EDH legality and color identity"""
    
    print("Loading scryfall data...")
    with open(input_file, 'r', encoding='utf-8') as f:
        all_cards = json.load(f)
    
    print(f"Total cards loaded: {len(all_cards)}")
    
    # Get valid color combinations
    valid_combinations = get_color_combinations()
    print(f"Valid color combinations: {[sorted(list(combo)) for combo in valid_combinations]}")
    
    # Filter cards
    filtered_cards = []
    color_counts = {}
    
    for card in all_cards:
        # Check if card has oracle text (required for tagging)
        if not card.get('oracle_text'):
            continue
            
        # Check if EDH legal
        if card.get('legalities', {}).get('commander') != 'legal':
            continue
        
        # Get color identity
        color_identity = set(card.get('color_identity', []))
        
        # Check if color identity matches any valid combination
        if color_identity in valid_combinations:
            filtered_cards.append(card)
            
            # Count by color combination
            combo_key = ''.join(sorted(color_identity)) if color_identity else 'Colorless'
            color_counts[combo_key] = color_counts.get(combo_key, 0) + 1
    
    print(f"\nFiltered cards: {len(filtered_cards)}")
    print("\nBreakdown by color combination:")
    for combo, count in sorted(color_counts.items()):
        print(f"  {combo}: {count} cards")
    
    # Save filtered cards
    print(f"\nSaving filtered cards to: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(filtered_cards, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Successfully saved {len(filtered_cards)} cards to {output_file}")
    
    # Show some examples
    print("\nFirst 10 filtered cards:")
    for i, card in enumerate(filtered_cards[:10]):
        color_id = ''.join(sorted(card.get('color_identity', []))) if card.get('color_identity') else 'Colorless'
        print(f"  {i+1}. {card['name']} ({color_id})")

def main():
    parser = argparse.ArgumentParser(description='Filter scryfall_oracle.json for EDH-legal B/W/R cards')
    parser.add_argument('--input', default='data/scryfall_oracle.json', 
                       help='Input JSON file (default: data/scryfall_oracle.json)')
    parser.add_argument('--output', default='data/bwr_cards.json', 
                       help='Output JSON file (default: data/bwr_cards.json)')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not input_path.exists():
        print(f"❌ Error: Input file {input_path} does not exist")
        return
    
    try:
        filter_cards(input_path, output_path)
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
