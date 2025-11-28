# Data Ingestion Pipeline

Automated pipeline for discovering and extracting health and social service resource data across the Dallas-Fort Worth area using Google Places API and OpenAI. We use this because DFW does not have a lot of ready-to-use datasets for these locations, and in order to properly automate this, we utitilize APIs. 

(Developer note: I have openAI credits I can spend, but you can swap out openAI)

## Overview

This pipeline automates the process of:

1. **Discovery**: Finding health clinics, mental health services, homeless shelters, and other community resources using Google Places API
2. **Collection**: Fetching website content for each discovered organization
3. **Extraction**: Using OpenAI's GPT models to extract structured data fields from website HTML
4. **Output**: Generating clean CSV files ready for manual review and S3 upload

## Directory Structure

```
data-ingestion/
├── README.md              # This file
├── config.py              # Configuration and settings
├── utils.py               # Utility functions
├── run_pipeline.py        # Main pipeline orchestrator
├── scripts/
│   ├── 1_discover_organizations.py   # Step 1: Google Places discovery
│   └── 2_scrape_and_extract.py       # Step 2: Web scraping + OpenAI extraction
├── samples/               # Sample CSV files
├── output/                # Generated CSV and JSON files
└── logs/                  # Log files from pipeline runs
```

## Setup

### 1. Install Dependencies

```bash
cd /your/path/to/CS4485
pip install -r requirements.txt
```

The key new dependencies are:
- `googlemaps` - For Google Places API
- `openai` - For OpenAI API
- `beautifulsoup4` - For HTML parsing
- `python-dotenv` - For environment variable management

### 2. Get API Keys

#### Google Places API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable the **Places API** and **Geocoding API**
4. Go to Credentials → Create Credentials → API Key
5. (Optional but recommended) Restrict the key to Places API and Geocoding API

#### OpenAI API Key

1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Sign up or log in
3. Go to [API Keys](https://platform.openai.com/api-keys)
4. Create a new secret key
5. Copy and save it securely

### 3. Configure Environment

Create a `.env` file in the `data-ingestion` directory:

```bash
cd data-ingestion
cat > .env << 'EOF'
# Google Places API Key
GOOGLE_PLACES_API_KEY=your_google_api_key_here

# OpenAI API Key  
OPENAI_API_KEY=your_openai_api_key_here

# Optional: Override defaults
# OPENAI_MODEL=gpt-4o-mini
# MAX_HTML_LENGTH=50000
# REQUEST_TIMEOUT=10
# RATE_LIMIT_DELAY=1.0
EOF
```

**Important**: Never commit the `.env` file to git! It's already in `.gitignore`.

### 4. Test Configuration

```bash
cd data-ingestion
python config.py
```

You should see ✓ marks next to both API keys.

## Usage

### Option 1: Run Complete Pipeline

The easiest way to run everything:

```bash
cd data-ingestion
python run_pipeline.py
```

This will:
1. Run discovery across all DFW locations
2. Scrape and extract data for all found organizations
3. Generate CSV files in the `output/` directory

### Option 2: Run Steps Individually

For more control, run each step separately:

#### Step 1: Discover Organizations

```bash
cd data-ingestion
python scripts/1_discover_organizations.py
```

This searches Google Places API for:
- Community health centers
- Mental health clinics
- Homeless services
- Free clinics
- FQHCs
- Substance abuse treatment
- And more...

Across locations:
- Dallas, Fort Worth, Arlington, Plano, Irving
- Richardson, Frisco, McKinney, Garland, Mesquite, Denton

**Output**: `output/discovered_orgs_YYYYMMDD_HHMMSS.json`

#### Step 2: Scrape and Extract

```bash
cd data-ingestion
python scripts/2_scrape_and_extract.py
```

This will:
1. Load the most recent discovery file
2. Let you choose to process all or a subset (useful for testing)
3. Scrape each organization's website
4. Use OpenAI to extract structured data
5. Generate CSV and JSON output

**Output**: 
- `output/extracted_resources_YYYYMMDD_HHMMSS.csv` - Main CSV file
- `output/extracted_resources_YYYYMMDD_HHMMSS.json` - JSON version
- `output/extraction_report_YYYYMMDD_HHMMSS.txt` - Summary report
- `output/extraction_errors_YYYYMMDD_HHMMSS.json` - Errors (if any)

## CSV Schema

The output CSV contains these fields:

| Field | Description | Example |
|-------|-------------|---------|
| `doc_id` | Unique document ID | `auto-dfw-a1b2c3d4` |
| `name` | Organization name | `Parkland Memorial Hospital` |
| `address` | Full street address | `5200 Harry Hines Blvd, Dallas, TX 75235` |
| `phone` | Phone number | `(214) 590-8000` |
| `website` | Website URL | `https://www.parklandhealth.org` |
| `services` | 1-2 sentence summary | `Safety-net hospital, emergency care, specialty clinics` |
| `population` | Who they serve | `Dallas County residents, uninsured individuals` |
| `eligibility` | Requirements | `Dallas County residents; accepts Medicaid/Medicare, sliding scale` |
| `intake` | How to access | `Call main line or request appointment online; ER 24/7` |
| `hours` | Operating hours | `Hospital: 24/7 emergency; clinics vary by department` |
| `capacity` | Capacity info (often empty) | `` |
| `cost` | Payment model | `Financial assistance and charity care programs available` |
| `contact_email` | Email address | `info@example.org` |
| `notes` | Additional info | `Primary safety-net hospital for Dallas County` |
TODO: add date created/last updated data

## Configuration

Edit `config.py` to customize:

### Search Locations

Add or modify cities in `SEARCH_LOCATIONS`:

```python
SEARCH_LOCATIONS = [
    {"name": "Dallas", "lat": 32.7767, "lng": -96.7970, "radius": 25000},
    # Add more locations...
]
```

### Search Queries

Modify `SEARCH_QUERIES` to find different types of organizations:

```python
SEARCH_QUERIES = [
    "community health center",
    "mental health clinic",
    # Add more queries...
]
```

### OpenAI Model

Default is `gpt-4o-mini` (cost-effective). For better quality, use `gpt-4o`:

```python
OPENAI_MODEL = "gpt-4o"
```

### Rate Limiting

Adjust delays between API calls:

```python
RATE_LIMIT_DELAY = 1.0  # seconds
```

## Cost Estimates

### Google Places API

- Text Search: $32 per 1,000 requests
- Place Details: $17 per 1,000 requests
- Estimated cost for full DFW run: **$20-40**

With 11 locations × 12 queries = 132 searches, finding ~200-300 unique places, you'll make:
- ~132 text searches (~$4.22)
- ~250 place details requests (~$4.25)
- **Total: ~$8.50**

(We have $300 free credits here) 

### OpenAI API

Using `gpt-4o-mini`:
- Input: $0.15 per 1M tokens
- Output: $0.60 per 1M tokens
- Average per organization: ~$0.01-0.02
- For 250 organizations: **$2.50-5.00**

**Total estimated cost per full run: ~$11-14**
(Laura has her credits for this)

### Cost Optimization Tips

1. **Test with subsets first**: Process 10-20 orgs to validate before running all
2. **Use filters**: Only process orgs with websites (saves on OpenAI calls)
3. **Increase rate limits carefully**: Don't get rate-limited
4. **Review discovery results**: Remove obvious non-matches before extraction

## Testing

### Test with Small Subset

```bash
cd data-ingestion
python scripts/2_scrape_and_extract.py
# When prompted, choose option 2 and enter "10"
```

This will process only 10 organizations for testing.

### Test Utilities

```bash
cd data-ingestion
python utils.py
```

### Test Configuration

```bash
cd data-ingestion
python config.py
```

## Post-Processing Workflow

After running the pipeline:

1. **Review the CSV**
   ```bash
   open output/extracted_resources_*.csv
   ```

2. **Spot-check 10-20 entries**
   - Verify accuracy of extracted data
   - Check that services descriptions make sense
   - Ensure eligibility and intake info is clear

3. **Fix Issues**
   - Manually edit problematic rows
   - Pay attention to hours, eligibility, intake fields
   - Ensure addresses are complete

4. **Merge with Existing Data**
   ```python
   import utils
   import config
   
   existing = utils.load_existing_resources(Path("samples/dfw_health_resources_health_only.csv"))
   new = utils.load_existing_resources(Path("output/extracted_resources_latest.csv"))
   merged = utils.merge_resources(existing, new)
   utils.save_resources_to_csv(merged, Path("output/merged_resources.csv"))
   ```

5. **Upload to S3**
   ```bash
   aws s3 cp output/merged_resources.csv s3://your-bucket/resources/
   ```

## Troubleshooting

### "Configuration validation failed"

- Check that `.env` file exists in `data-ingestion/` directory
- Verify API keys are correct (no extra spaces, quotes, etc.)

### "Google Places API error"

- Verify Places API is enabled in Google Cloud Console
- Check API key restrictions aren't too strict
- Ensure billing is enabled on your Google Cloud project

### "OpenAI rate limit error"

- You're hitting rate limits. Increase `RATE_LIMIT_DELAY` in config
- Or upgrade your OpenAI account tier

### "Timeout scraping website"

- Some websites are slow or blocking requests
- The pipeline will log warnings and continue
- These orgs will have minimal data (fallback)

### "JSON decode error"

- OpenAI sometimes returns invalid JSON
- The pipeline will retry with fallback data
- Check logs for details

### Empty services/eligibility fields

- Website might not have clear info
- OpenAI is being conservative (returns empty vs guessing)
- Manually review and fill in if you have info

## Advanced Usage

### Custom Extraction Prompt

Edit the `EXTRACTION_PROMPT` in `scripts/2_scrape_and_extract.py` to customize what OpenAI extracts and how.

### Add Custom Post-Processing

Create a new script `scripts/3_post_process.py` to:
- Geocode addresses
- Validate phone numbers
- Check website availability
- Add county/region tags
- etc.

### Scheduled Runs

Set up a cron job to refresh data monthly:

```bash
# Add to crontab
0 2 1 * * cd /path/to/data-ingestion && python run_pipeline.py >> logs/cron.log 2>&1
```

## Sample Data

The `samples/` directory contains example CSV files:

- `dfw_health_resources_health_only.csv` - 51 health resources
- `mh_dfw_resources.csv` - 21 mental health resources

Use these as reference for data quality and formatting.

## Support

For issues or questions:

1. Check the logs in `logs/` directory
2. Review error JSON files in `output/`
3. Consult OpenAI and Google Places API documentation
4. Modify configuration and retry



