#!/usr/bin/env python3
"""
Step 2: Scrape organization websites and extract structured data using OpenAI.

This script takes the organizations discovered in step 1, grabs the information from their websites, 
and extracts structured information into CSV format.
and uses OpenAI's API to extract structured information into CSV format.
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Optional
import time
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from bs4 import BeautifulSoup
from openai import OpenAI

import config
import utils


# Extraction prompt template
EXTRACTION_PROMPT = """You are helping build a comprehensive homeless and health resource directory for the Dallas-Fort Worth area.

Given the HTML content from an organization's website, extract the following fields and return them as VALID JSON.

Required fields (use empty string "" if not found):
- name: Organization or clinic name
- address: Full street address (street, city, state, zip)
- phone: Primary phone number
- website: Website URL
- services: 1-2 sentence summary of services offered (be concise and specific)
- population: Who they primarily serve (e.g., "uninsured adults", "homeless individuals", "all ages")
- eligibility: Criteria like income limits, residency requirements, insurance accepted (be specific)
- intake: How clients access services (e.g., "call for appointment", "walk-in", "referral required")
- hours: Operating hours (days and times)
- capacity: If mentioned, any capacity limits or waitlist info (usually empty)
- cost: Payment model (e.g., "Free", "Sliding scale", "Medicaid accepted", "Insurance required")
- contact_email: Email address if available
- notes: Any other critical info in 1-2 short phrases (e.g., "FQHC", "Faith-based", "Requires ID")

Important guidelines:
1. Return ONLY valid JSON - no commentary, no markdown, no code blocks
2. If a field is not clearly stated in the HTML, use an empty string ""
3. Be concise - services should be 1-2 sentences max, notes should be brief
4. For eligibility and intake, capture the key requirements only
5. If the HTML is empty or doesn't contain useful info, still return valid JSON with the fallback data

Fallback data (use if HTML is insufficient):
Name: {fallback_name}
Website: {fallback_website}

HTML content:
{html_content}

Return ONLY the JSON object with all required fields."""


def scrape_website(url: str, logger) -> str:
    """
    Scrape HTML content from a website.
    
    Args:
        url: Website URL
        logger: Logger instance
    
    Returns:
        HTML content as string (truncated to MAX_HTML_LENGTH)
    """
    if not url:
        return ""
    
    try:
        headers = {
            'User-Agent': config.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        response = requests.get(
            url,
            headers=headers,
            timeout=config.REQUEST_TIMEOUT,
            allow_redirects=True
        )
        response.raise_for_status()
        
        # Parse with BeautifulSoup to clean up
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "noscript"]):
            script.decompose()
        
        # Get text content
        text = soup.get_text(separator=' ', strip=True)
        
        # Truncate to avoid huge token costs
        if len(text) > config.MAX_HTML_LENGTH:
            text = text[:config.MAX_HTML_LENGTH]
            logger.debug(f"  Truncated HTML from {url} to {config.MAX_HTML_LENGTH} chars")
        
        logger.debug(f"  Scraped {len(text)} chars from {url}")
        return text
    
    except requests.exceptions.Timeout:
        logger.warning(f"  Timeout scraping {url}")
        return ""
    
    except requests.exceptions.RequestException as e:
        logger.warning(f"  Error scraping {url}: {e}")
        return ""
    
    except Exception as e:
        logger.error(f"  Unexpected error scraping {url}: {e}")
        return ""


def extract_with_openai(
    html: str,
    fallback_name: str,
    fallback_website: str,
    client: OpenAI,
    logger
) -> Optional[Dict]:
    """
    Use OpenAI to extract structured fields from HTML content.
    
    Args:
        html: HTML content (cleaned text)
        fallback_name: Name to use if extraction fails
        fallback_website: Website to use if extraction fails
        client: OpenAI client
        logger: Logger instance
    
    Returns:
        Dictionary with extracted fields, or None if extraction fails
    """
    try:
        # Build the prompt
        prompt = EXTRACTION_PROMPT.format(
            fallback_name=fallback_name,
            fallback_website=fallback_website,
            html_content=html if html else "[No HTML content available]"
        )
        
        # Call OpenAI
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a data extraction assistant. Return only valid JSON with no additional text."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=config.OPENAI_TEMPERATURE,
            max_tokens=config.OPENAI_MAX_TOKENS,
        )
        
        # Extract the response
        content = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if content.startswith('```'):
            # Remove opening ```json or ```
            content = content.split('\n', 1)[1] if '\n' in content else content[3:]
            # Remove closing ```
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
        
        # Parse JSON
        data = json.loads(content)
        
        # Ensure all required fields are present
        for field in config.CSV_FIELDNAMES:
            if field not in data:
                data[field] = ""
        
        # Clean text fields
        for field in data:
            if isinstance(data[field], str):
                data[field] = utils.clean_text(data[field])
        
        logger.debug(f"  ✓ Successfully extracted data")
        return data
    
    except json.JSONDecodeError as e:
        logger.error(f"  JSON decode error: {e}")
        logger.error(f"  Content: {content[:200]}...")
        return None
    
    except Exception as e:
        logger.error(f"  Error with OpenAI extraction: {e}")
        return None


def process_organization(
    org: Dict,
    client: OpenAI,
    logger,
    doc_id_prefix: str = "auto-dfw"
) -> Optional[Dict]:
    """
    Process a single organization: scrape website and extract data.
    
    Args:
        org: Organization dictionary from discovery step
        client: OpenAI client
        logger: Logger instance
        doc_id_prefix: Prefix for document IDs
    
    Returns:
        Dictionary with extracted resource data, or None if processing fails
    """
    name = org.get('name', 'Unknown')
    website = org.get('website', '')
    
    logger.info(f"\nProcessing: {name}")
    logger.info(f"  Website: {website if website else '(none)'}")
    
    # Scrape website
    html = ""
    if website:
        html = scrape_website(website, logger)
        # Rate limit to be nice
        utils.rate_limit(0.5)
    else:
        logger.warning(f"  No website - using minimal data")
    
    # Extract data with OpenAI
    extracted = extract_with_openai(
        html,
        fallback_name=name,
        fallback_website=website,
        client=client,
        logger=logger
    )
    
    if not extracted:
        # Fallback to basic information
        logger.warning(f"  Extraction failed - using fallback data")
        extracted = {
            'name': name,
            'address': org.get('address', ''),
            'phone': org.get('phone', ''),
            'website': website,
            'services': '',
            'population': '',
            'eligibility': '',
            'intake': '',
            'hours': '',
            'capacity': '',
            'cost': '',
            'contact_email': '',
            'notes': f"Found via: {org.get('found_via_query', 'unknown query')}"
        }
    
    # Generate doc_id
    extracted['doc_id'] = utils.generate_doc_id(
        extracted.get('name', name),
        extracted.get('address', org.get('address', '')),
        prefix=doc_id_prefix
    )
    
    # Normalize fields
    if not extracted.get('name'):
        extracted['name'] = name
    if not extracted.get('address'):
        extracted['address'] = org.get('address', '')
    if not extracted.get('phone'):
        extracted['phone'] = org.get('phone', '')
    if not extracted.get('website'):
        extracted['website'] = website
    
    # Normalize phone and website
    extracted['phone'] = utils.normalize_phone(extracted['phone'])
    extracted['website'] = utils.normalize_url(extracted['website'])
    
    # Apply rate limiting for OpenAI
    utils.rate_limit(config.RATE_LIMIT_DELAY)
    
    return extracted


def main():
    """Main execution function."""
    logger = utils.setup_logging("scrape_and_extract")
    
    logger.info("Starting web scraping and data extraction pipeline")
    logger.info("="*80)
    
    # Validate configuration
    if not config.validate_config():
        logger.error("Configuration validation failed!")
        return 1
    
    # Find the most recent discovery file
    discovery_files = sorted(config.OUTPUT_DIR.glob("discovered_orgs_*.json"))
    if not discovery_files:
        logger.error("No discovery files found! Run 1_discover_organizations.py first.")
        return 1
    
    discovery_file = discovery_files[-1]
    logger.info(f"Loading organizations from: {discovery_file}")
    
    # Load discovered organizations
    orgs = utils.load_json(discovery_file, logger)
    if not orgs:
        logger.error("No organizations to process!")
        return 1
    
    logger.info(f"Loaded {len(orgs)} organizations")
    
    # Ask user if they want to process all or a subset (for testing)
    print("\n" + "="*80)
    print(f"Found {len(orgs)} organizations to process")
    print("="*80)
    print("\nOptions:")
    print("  1. Process all organizations")
    print("  2. Process first N organizations (for testing)")
    print("  3. Process organizations with websites only")
    
    choice = input("\nEnter choice (1-3, default=1): ").strip() or "1"
    
    if choice == "2":
        n = input("How many to process? ").strip()
        try:
            n = int(n)
            orgs = orgs[:n]
            logger.info(f"Processing first {n} organizations")
        except ValueError:
            logger.error("Invalid number, processing all")
    elif choice == "3":
        orgs = [o for o in orgs if o.get('website')]
        logger.info(f"Processing {len(orgs)} organizations with websites")
    
    # Initialize OpenAI client
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    
    # Process each organization
    extracted_resources = []
    errors = []
    
    total = len(orgs)
    logger.info(f"\n{'='*80}")
    logger.info(f"Starting extraction for {total} organizations")
    logger.info(f"{'='*80}")
    
    for i, org in enumerate(orgs, 1):
        logger.info(f"\n[{i}/{total}] " + "="*60)
        
        try:
            resource = process_organization(org, client, logger)
            if resource:
                extracted_resources.append(resource)
            else:
                errors.append({
                    'name': org.get('name'),
                    'website': org.get('website'),
                    'error': 'Extraction failed'
                })
        
        except Exception as e:
            logger.error(f"Failed to process {org.get('name')}: {e}")
            errors.append({
                'name': org.get('name'),
                'website': org.get('website'),
                'error': str(e)
            })
    
    # Save results
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    if extracted_resources:
        # Deduplicate
        extracted_resources = utils.deduplicate_resources(extracted_resources, logger)
        
        # Save to CSV
        csv_output_path = config.OUTPUT_DIR / f"extracted_resources_{timestamp}.csv"
        utils.save_resources_to_csv(extracted_resources, csv_output_path, logger)
        
        # Also save as JSON for reference
        json_output_path = config.OUTPUT_DIR / f"extracted_resources_{timestamp}.json"
        utils.save_json(extracted_resources, json_output_path, logger)
        
        # Create summary report
        report_path = config.OUTPUT_DIR / f"extraction_report_{timestamp}.txt"
        utils.create_summary_report(extracted_resources, report_path, logger)
    
    # Save errors if any
    if errors:
        errors_path = config.OUTPUT_DIR / f"extraction_errors_{timestamp}.json"
        utils.save_json(errors, errors_path, logger)
        logger.warning(f"\n{len(errors)} organizations failed - see {errors_path}")
    
    # Final summary
    logger.info("\n" + "="*80)
    logger.info("EXTRACTION COMPLETE")
    logger.info("="*80)
    logger.info(f"Successfully extracted: {len(extracted_resources)}")
    logger.info(f"Failed: {len(errors)}")
    logger.info(f"Success rate: {len(extracted_resources)/total*100:.1f}%")
    
    if extracted_resources:
        logger.info(f"\nOutput saved to: {csv_output_path}")
        logger.info(f"JSON saved to: {json_output_path}")
        logger.info(f"Report saved to: {report_path}")
    
    # Laura does this part manually before S3 uploads :3 
    logger.info("\nNext step: Manually review the CSV, spot-check entries/duplicates, and upload to S3")
    logger.info("="*80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

