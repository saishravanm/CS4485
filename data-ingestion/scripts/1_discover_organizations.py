#!/usr/bin/env python3
"""
Step 1: Discover organizations using Google Places API.

This script searches for health and social service organizations across the DFW area
using Google Places API and saves the results to a JSON file for further processing.
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Set
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import googlemaps
from googlemaps.exceptions import ApiError

import config
import utils


def search_places(
    gmaps: googlemaps.Client,
    query: str,
    location: Dict,
    logger
) -> List[Dict]:
    """
    Search for places using Google Places API.
    
    Args:
        gmaps: Google Maps client
        query: Search query
        location: Dictionary with 'name', 'lat', 'lng', 'radius'
        logger: Logger instance
    
    Returns:
        List of place dictionaries
    """
    logger.info(f"Searching '{query}' near {location['name']}...")
    
    try:
        results = gmaps.places(
            query=query,
            location=(location['lat'], location['lng']),
            radius=location['radius']
        )
        
        places = results.get('results', [])
        logger.info(f"  Found {len(places)} places")
        
        # Apply rate limiting
        utils.rate_limit(0.5)  # Be nice to the API
        
        return places
    
    except ApiError as e:
        logger.error(f"API error for '{query}' near {location['name']}: {e}")
        return []
    
    except Exception as e:
        logger.error(f"Unexpected error for '{query}' near {location['name']}: {e}")
        return []


def get_place_details(gmaps: googlemaps.Client, place_id: str, logger) -> Dict:
    """
    Get detailed information about a place.
    
    Args:
        gmaps: Google Maps client
        place_id: Google Place ID
        logger: Logger instance
    
    Returns:
        Dictionary with place details
    """
    try:
        result = gmaps.place(place_id=place_id)
        utils.rate_limit(0.3)
        return result.get('result', {})
    
    except Exception as e:
        logger.error(f"Error getting details for place {place_id}: {e}")
        return {}


def extract_org_info(place: Dict, location_name: str) -> Dict:
    """
    Extract relevant organization information from Google Places result.
    
    Args:
        place: Place dictionary from Google Places API
        location_name: Name of the search location
    
    Returns:
        Dictionary with extracted information
    """
    return {
        'name': place.get('name', ''),
        'address': place.get('formatted_address', ''),
        'phone': place.get('formatted_phone_number', ''),
        'website': place.get('website', ''),
        'place_id': place.get('place_id', ''),
        'types': place.get('types', []),
        'rating': place.get('rating'),
        'user_ratings_total': place.get('user_ratings_total'),
        'lat': place.get('geometry', {}).get('location', {}).get('lat'),
        'lng': place.get('geometry', {}).get('location', {}).get('lng'),
        'found_via_query': '',  # Will be set by caller
        'found_in_location': location_name,
        'business_status': place.get('business_status', ''),
    }


def discover_organizations(logger) -> List[Dict]:
    """
    Main function to discover organizations across DFW area.
    
    Args:
        logger: Logger instance
    
    Returns:
        List of discovered organizations
    """
    if not config.GOOGLE_PLACES_API_KEY:
        logger.error("Google Places API key not configured!")
        return []
    
    # Initialize Google Maps client
    gmaps = googlemaps.Client(key=config.GOOGLE_PLACES_API_KEY)
    
    all_orgs = []
    seen_place_ids: Set[str] = set()
    
    total_searches = len(config.SEARCH_LOCATIONS) * len(config.SEARCH_QUERIES)
    search_count = 0
    
    logger.info(f"Starting discovery across {len(config.SEARCH_LOCATIONS)} locations")
    logger.info(f"Using {len(config.SEARCH_QUERIES)} search queries")
    logger.info(f"Total searches to perform: {total_searches}")
    logger.info("="*80)
    
    # Search each location with each query
    for location in config.SEARCH_LOCATIONS:
        logger.info(f"\n{'='*80}")
        logger.info(f"Location: {location['name']}")
        logger.info(f"{'='*80}")
        
        for query in config.SEARCH_QUERIES:
            search_count += 1
            logger.info(f"\n[{search_count}/{total_searches}] {query}")
            
            # Get basic place results
            places = search_places(gmaps, query, location, logger)
            
            # Process each place
            for place in places:
                place_id = place.get('place_id')
                
                # Skip if we've already seen this place
                if place_id in seen_place_ids:
                    continue
                
                seen_place_ids.add(place_id)
                
                # Get detailed information
                logger.debug(f"  Getting details for: {place.get('name')}")
                detailed_place = get_place_details(gmaps, place_id, logger)
                
                if detailed_place:
                    # Merge basic and detailed information
                    place.update(detailed_place)
                
                # Extract organization info
                org_info = extract_org_info(place, location['name'])
                org_info['found_via_query'] = query
                
                all_orgs.append(org_info)
                logger.debug(f"    ✓ {org_info['name']}")
    
    logger.info(f"\n{'='*80}")
    logger.info(f"Discovery complete!")
    logger.info(f"Total unique organizations found: {len(all_orgs)}")
    logger.info(f"{'='*80}")
    
    return all_orgs


def filter_relevant_orgs(orgs: List[Dict], logger) -> List[Dict]:
    """
    Filter organizations to keep only those likely to be relevant resources.
    
    Args:
        orgs: List of organization dictionaries
        logger: Logger instance
    
    Returns:
        Filtered list of organizations
    """
    logger.info("\nFiltering organizations...")
    
    # Types that indicate relevant health/social services
    relevant_types = {
        'health', 'hospital', 'doctor', 'clinic', 'pharmacy',
        'mental_health', 'psychologist', 'counseling',
        'social_service', 'community_center', 'nonprofit',
        'government', 'public_health',
    }
    
    # Keywords in name that suggest relevance
    relevant_keywords = {
        'health', 'clinic', 'hospital', 'medical', 'mental',
        'counseling', 'therapy', 'service', 'center', 'shelter',
        'housing', 'food', 'assistance', 'support', 'crisis',
        'community', 'family', 'child', 'women', 'veteran',
        'homeless', 'recovery', 'addiction', 'substance',
    }
    
    filtered = []
    
    for org in orgs:
        # Check if business is operational
        if org.get('business_status') not in ['OPERATIONAL', '']:
            continue
        
        # Check types
        org_types = [t.lower() for t in org.get('types', [])]
        has_relevant_type = any(
            any(rt in ot for rt in relevant_types)
            for ot in org_types
        )
        
        # Check name
        name_lower = org.get('name', '').lower()
        has_relevant_keyword = any(kw in name_lower for kw in relevant_keywords)
        
        # Keep if it matches type or keyword criteria
        if has_relevant_type or has_relevant_keyword:
            filtered.append(org)
    
    logger.info(f"Kept {len(filtered)} relevant organizations (filtered out {len(orgs) - len(filtered)})")
    
    return filtered


def main():
    """Main execution function."""
    logger = utils.setup_logging("discover_organizations")
    
    logger.info("Starting organization discovery pipeline")
    logger.info("="*80)
    
    # Validate configuration
    if not config.validate_config():
        logger.error("Configuration validation failed!")
        return 1
    
    # Discover organizations
    orgs = discover_organizations(logger)
    
    if not orgs:
        logger.error("No organizations discovered!")
        return 1
    
    # Filter to relevant organizations
    filtered_orgs = filter_relevant_orgs(orgs, logger)
    
    # Save raw results
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    raw_output_path = config.OUTPUT_DIR / f"discovered_orgs_raw_{timestamp}.json"
    utils.save_json(filtered_orgs, raw_output_path, logger)
    
    # Also save a simplified version for the next step
    simplified = []
    for org in filtered_orgs:
        simplified.append({
            'name': org['name'],
            'address': org['address'],
            'phone': utils.normalize_phone(org.get('phone', '')),
            'website': utils.normalize_url(org.get('website', '')),
            'place_id': org['place_id'],
            'found_via_query': org['found_via_query'],
            'found_in_location': org['found_in_location'],
        })
    
    simplified_output_path = config.OUTPUT_DIR / f"discovered_orgs_{timestamp}.json"
    utils.save_json(simplified, simplified_output_path, logger)
    
    # Create a summary
    logger.info("\n" + "="*80)
    logger.info("DISCOVERY SUMMARY")
    logger.info("="*80)
    logger.info(f"Total organizations discovered: {len(filtered_orgs)}")
    logger.info(f"Organizations with websites: {sum(1 for o in filtered_orgs if o.get('website'))}")
    logger.info(f"Organizations with phone numbers: {sum(1 for o in filtered_orgs if o.get('phone'))}")
    logger.info("")
    logger.info(f"Raw results saved to: {raw_output_path}")
    logger.info(f"Simplified results saved to: {simplified_output_path}")
    logger.info("")
    logger.info("Next step: Run 2_scrape_and_extract.py to extract detailed information")
    logger.info("="*80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

