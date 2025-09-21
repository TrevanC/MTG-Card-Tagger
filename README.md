# MTG Card Tagger

An AI-powered tool for tagging Magic: The Gathering cards with EDH (Commander) deckbuilding metadata using OpenAI's GPT models.

## Features

- **Multiple Processing Modes**: Sequential, async parallel, and batch processing
- **EDH Filtering**: Process only EDH/Commander legal cards
- **Color Filtering**: Filter by color identity (mono, dual, etc.)
- **Progress Tracking**: Real-time progress bars with time estimates
- **File Splitting**: Automatically split large outputs into manageable files
- **Resume Capability**: Resume interrupted processing sessions
- **Incremental Saving**: No data loss on interruption

## Installation

1. Install required dependencies:
```bash
pip install openai tqdm PyYAML
```

2. Set up your OpenAI API key:
```bash
export OPENAI_API_KEY="your-api-key-here"
```

## Usage

### Basic Command Structure

```bash
cd src
python3 tag_cards.py [OPTIONS]
```

### Command Options

#### Input/Output Options
- `--input INPUT`: Input JSON file of cards (default: `../data/scryfall_oracle.json`)
- `--output OUTPUT`: Output JSONL file (default: `../output/tagged_cards.jsonl`)
- `--taxonomy TAXONOMY`: Taxonomy YAML file (default: `taxonomy.slim.yaml`)
- `--schema SCHEMA`: JSON schema file (default: `card_tag.slim.schema.json`)

#### Processing Options
- `--model MODEL`: OpenAI model to use (default: `gpt-4o-mini`)
- `--async`: Use async parallel mode for faster processing
- `--concurrency CONCURRENCY`: Number of concurrent requests in async mode (default: 10)
- `--batch-size BATCH_SIZE`: Cards per batch (0 = disabled, default: 0)

#### Filtering Options
- `--edh-only`: Only process EDH/Commander legal cards
- `--colors [{W,U,B,R,G} ...]`: Filter by color identity (e.g., `--colors W U` for Azorius)
- `--colorless`: Include colorless cards (no color identity)

#### File Management Options
- `--split-size SPLIT_SIZE`: Create new file every N cards (0 = disabled, default: 0)
- `--resume`: Resume from existing output file (skip already processed cards)

## Examples

### Process All EDH-Legal Cards
```bash
python3 tag_cards.py --edh-only
```

### Process Mono-Red EDH Cards with Batch Processing
```bash
python3 tag_cards.py --edh-only --colors R --batch-size 10 --split-size 5000 --output ../output/red_cards.jsonl
```

### Process Azorius (WU) Cards with Async Processing
```bash
python3 tag_cards.py --edh-only --colors W U --async --concurrency 5
```

### Process Colorless Cards with File Splitting
```bash
python3 tag_cards.py --edh-only --colorless --split-size 1000
```

### Resume Interrupted Processing
```bash
python3 tag_cards.py --edh-only --colors B --resume
```

### Use Different Model
```bash
python3 tag_cards.py --edh-only --colors G --model gpt-4o
```

### batch process mono color
```bash
python3 tag_cards.py --edh-only --batch-size 5 --model gpt-5-nano  --output ../output/green_cards.jsonl --colors G
python3 tag_cards.py --edh-only --batch-size 5 --model gpt-5-nano  --output ../output/blue_cards.jsonl --colors U
python3 tag_cards.py --edh-only --batch-size 5 --model gpt-5-nano  --output ../output/orzhov_cards.jsonl --colors B W
python3 tag_cards.py --edh-only --batch-size 5 --model gpt-5-nano  --output ../output/rakdos_cards.jsonl --colors B R
python3 tag_cards.py --edh-only --batch-size 5 --model gpt-5-nano  --output ../output/boros_cards.jsonl --colors R W
python3 tag_cards.py --edh-only --batch-size 5 --model gpt-5-nano  --output ../output/golgari_cards.jsonl --colors G B
```

## Processing Modes

### Sequential Mode (Default)
- Most accurate: Each card gets individual attention
- Slower but highest quality results
- Best for: Small datasets, maximum accuracy

### Async Mode (`--async`)
- Parallel processing with configurable concurrency
- Faster than sequential
- Best for: Medium datasets, balanced speed/accuracy

### Batch Mode (`--batch-size N`)
- Multiple cards per API call
- Most efficient API usage
- Best for: Large datasets, cost optimization

## File Splitting

When using `--split-size N`, files are automatically split:

**Example**: `--output red_cards.jsonl --split-size 1000`
- `red_cards.jsonl` (first 1,000 cards)
- `red_cards_part2.jsonl` (next 1,000 cards)
- `red_cards_part3.jsonl` (next 1,000 cards)
- etc.

## Progress Tracking

The tool displays real-time progress bars showing:
- Current progress (X/Y cards)
- Percentage complete
- Estimated time remaining
- Processing speed
- Success count

## Output Format

Results are saved as JSONL (JSON Lines) with each line containing a complete tagged card:

```json
{
  "name": "Lightning Bolt",
  "oracle_id": "abc123",
  "function_primary": ["removal"],
  "function_secondary": [],
  "resource_axis": [],
  "interaction_axis": ["creatures"],
  "target_axis": ["any"],
  "synergy": {"mechanics": []},
  "derived_fields": {
    "repeatability": "one_shot",
    "scalability": "low",
    "synergy_intensity": "filler"
  },
  "confidence": {
    "function_primary": 0.9,
    "function_secondary": 0,
    "resource_axis": 0,
    "interaction_axis": 0.8,
    "target_axis": 0.9,
    "synergy_mechanics": 0,
    "repeatability": 0.9,
    "scalability": 0.8,
    "synergy_intensity": 0.7
  },
  "review": {"status": "unreviewed"},
  "notes": ""
}
```

## Data Statistics

- **Total cards**: ~35,749
- **Cards with oracle text**: ~32,279
- **EDH-legal cards**: ~28,592
- **Mono-color cards**: ~4,200-4,600 each color
- **Colorless cards**: ~2,598

## Troubleshooting

### Common Issues

1. **"Please install openai"**: Run `pip install openai`
2. **API key not set**: Set `OPENAI_API_KEY` environment variable
3. **Rate limiting**: Reduce `--concurrency` or use `--batch-size`
4. **Memory issues**: Use `--split-size` to create smaller files

### Performance Tips

- Use `--batch-size 10` for most efficient API usage
- Use `--async --concurrency 5` for balanced speed/rate limits
- Use `--split-size 5000` for manageable file sizes
- Start with small datasets to test your setup

## Model Recommendations

| Model | Speed | Cost | Quality | Best For |
|-------|-------|------|---------|----------|
| `gpt-5-nano` | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | **Default choice** |
| `gpt-5` | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | Highest accuracy |


## Experimentation updates

### 9/20/2025

- finalized [tagging taxonomy](src/taxonomy.slim.yaml)
- finalized [output schema](src/card_tag.slim.schema.json)
- model of choice: `gpt-5-nano`
- running parameters `--batch-size 5`
- collected tags for ~20k cards in about 18 hours

```
% wc -l output/*.jsonl
    4303 output/black_cards.jsonl
    2006 output/blue_cards.jsonl
     367 output/boros_cards.jsonl
     347 output/golgari_cards.jsonl
    4153 output/green_cards.jsonl
     349 output/orzhov_cards.jsonl
     438 output/rakdos_cards.jsonl
    4249 output/red_cards.jsonl
    4332 output/white_cards.jsonl
      98 output/WUBRG_cards.jsonl
   20642 total
```


## License

This project is for educational and research purposes. Please respect OpenAI's usage policies and Magic: The Gathering's intellectual property.