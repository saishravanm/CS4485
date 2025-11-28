"""
Utility functions for data ingestion pipeline.
"""

import csv
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import hashlib

import config


def setup_logging(log_name: str = "data_ingestion") -> logging.Logger:
    """Set up logging to file and console."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = config.LOGS_DIR / f"{log_name}_{timestamp}.log"
    
    logger = logging.getLogger(log_name)
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    logger.handlers = []
    
    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logger.info(f"Logging initialized. Log file: {log_file}")
    return logger


def generate_doc_id(name: str, address: str, prefix: str = "auto-dfw") -> str:
    """
    Generate a unique document ID based on name and address.
    
    Args:
        name: Organization name
        address: Organization address
        prefix: Prefix for the ID
    
    Returns:
        Unique document ID
    """
    # Create hash from name + address for uniqueness
    content = f"{name.lower().strip()}{address.lower().strip()}"
    hash_digest = hashlib.md5(content.encode()).hexdigest()[:8]
    return f"{prefix}-{hash_digest}"


def normalize_phone(phone: str) -> str:
    """Normalize phone number format."""
    if not phone:
        return ""
    
    # Remove common formatting characters
    digits = ''.join(c for c in phone if c.isdigit())
    
    # Format as (XXX) XXX-XXXX if we have 10 digits
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    
    return phone  # Return original if we can't parse


def normalize_url(url: str) -> str:
    """Normalize URL format."""
    if not url:
        return ""
    
    url = url.strip().lower()
    
    # Add https:// if no protocol
    if url and not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    
    # Remove trailing slash
    url = url.rstrip('/')
    
    return url


def load_existing_resources(csv_path: Path) -> List[Dict[str, str]]:
    """Load existing resources from a CSV file."""
    resources = []
    
    if not csv_path.exists():
        return resources
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            resources.append(row)
    
    return resources


def save_resources_to_csv(
    resources: List[Dict[str, str]], 
    output_path: Path,
    logger: Optional[logging.Logger] = None
) -> None:
    """
    Save resources to CSV file.
    
    Args:
        resources: List of resource dictionaries
        output_path: Path to output CSV file
        logger: Optional logger instance
    """
    if logger:
        logger.info(f"Saving {len(resources)} resources to {output_path}")
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=config.CSV_FIELDNAMES)
        writer.writeheader()
        
        for resource in resources:
            # Ensure all fields are present
            row = {field: resource.get(field, "") for field in config.CSV_FIELDNAMES}
            writer.writerow(row)
    
    if logger:
        logger.info(f"Successfully saved to {output_path}")


def deduplicate_resources(
    resources: List[Dict[str, str]], 
    logger: Optional[logging.Logger] = None
) -> List[Dict[str, str]]:
    """
    Deduplicate resources based on name, address, and website.
    
    Args:
        resources: List of resource dictionaries
        logger: Optional logger instance
    
    Returns:
        Deduplicated list of resources
    """
    seen = set()
    unique_resources = []
    duplicates = 0
    
    for resource in resources:
        # Create a key from name, address, and website
        key = (
            resource.get('name', '').lower().strip(),
            resource.get('address', '').lower().strip(),
            resource.get('website', '').lower().strip()
        )
        
        if key not in seen:
            seen.add(key)
            unique_resources.append(resource)
        else:
            duplicates += 1
    
    if logger:
        logger.info(f"Removed {duplicates} duplicates. {len(unique_resources)} unique resources remain.")
    
    return unique_resources


def merge_resources(
    existing: List[Dict[str, str]], 
    new: List[Dict[str, str]],
    logger: Optional[logging.Logger] = None
) -> List[Dict[str, str]]:
    """
    Merge new resources with existing ones, avoiding duplicates.
    
    Args:
        existing: List of existing resource dictionaries
        new: List of new resource dictionaries
        logger: Optional logger instance
    
    Returns:
        Merged and deduplicated list
    """
    if logger:
        logger.info(f"Merging {len(existing)} existing with {len(new)} new resources")
    
    # Combine and deduplicate
    all_resources = existing + new
    merged = deduplicate_resources(all_resources, logger)
    
    return merged


def rate_limit(delay: float = None) -> None:
    """
    Apply rate limiting delay.
    
    Args:
        delay: Seconds to wait (defaults to config.RATE_LIMIT_DELAY)
    """
    if delay is None:
        delay = config.RATE_LIMIT_DELAY
    time.sleep(delay)


def clean_text(text: str) -> str:
    """Clean and normalize text fields."""
    if not text:
        return ""
    
    # Replace multiple spaces with single space
    text = ' '.join(text.split())
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text


def save_json(data: Any, filepath: Path, logger: Optional[logging.Logger] = None) -> None:
    """Save data as JSON file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    if logger:
        logger.info(f"Saved JSON to {filepath}")


def load_json(filepath: Path, logger: Optional[logging.Logger] = None) -> Any:
    """Load data from JSON file."""
    if not filepath.exists():
        if logger:
            logger.warning(f"JSON file not found: {filepath}")
        return None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if logger:
        logger.info(f"Loaded JSON from {filepath}")
    
    return data


def create_summary_report(
    resources: List[Dict[str, str]], 
    output_path: Path,
    logger: Optional[logging.Logger] = None
) -> None:
    """
    Create a summary report of the ingestion results.
    
    Args:
        resources: List of resource dictionaries
        output_path: Path to output report file
        logger: Optional logger instance
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report = [
        "="*80,
        f"Data Ingestion Summary Report",
        f"Generated: {timestamp}",
        "="*80,
        "",
        f"Total Resources: {len(resources)}",
        "",
    ]
    
    # Count resources by various metrics
    with_phone = sum(1 for r in resources if r.get('phone'))
    with_website = sum(1 for r in resources if r.get('website'))
    with_email = sum(1 for r in resources if r.get('contact_email'))
    with_hours = sum(1 for r in resources if r.get('hours'))
    
    report.extend([
        "Field Completeness:",
        f"  - With phone: {with_phone} ({with_phone/len(resources)*100:.1f}%)",
        f"  - With website: {with_website} ({with_website/len(resources)*100:.1f}%)",
        f"  - With email: {with_email} ({with_email/len(resources)*100:.1f}%)",
        f"  - With hours: {with_hours} ({with_hours/len(resources)*100:.1f}%)",
        "",
    ])
    
    # Sample entries
    report.extend([
        "Sample Resources (first 5):",
        ""
    ])
    
    for i, resource in enumerate(resources[:5], 1):
        report.append(f"{i}. {resource.get('name', 'N/A')}")
        report.append(f"   Address: {resource.get('address', 'N/A')}")
        report.append(f"   Website: {resource.get('website', 'N/A')}")
        report.append("")
    
    report.append("="*80)
    
    report_text = "\n".join(report)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    if logger:
        logger.info(f"Summary report saved to {output_path}")
        # Also print to console
        print("\n" + report_text)


if __name__ == "__main__":
    # Test utilities
    logger = setup_logging("test")
    logger.info("Testing utilities...")
    
    # Test ID generation
    doc_id = generate_doc_id("Test Clinic", "123 Main St, Dallas, TX")
    print(f"Generated ID: {doc_id}")
    
    # Test phone normalization
    phones = ["2145551234", "214-555-1234", "(214) 555-1234", "1-214-555-1234"]
    for phone in phones:
        print(f"{phone} -> {normalize_phone(phone)}")
    
    # Test URL normalization
    urls = ["example.com", "www.example.com", "http://example.com/", "https://example.com"]
    for url in urls:
        print(f"{url} -> {normalize_url(url)}")
    
    print("\nUtilities test complete!")

