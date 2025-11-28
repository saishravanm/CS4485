#!/usr/bin/env python3
"""
Utility script to merge CSV files and remove duplicates.

Usage:
    python merge_csvs.py file1.csv file2.csv [file3.csv ...] -o output.csv
"""

import sys
import argparse
from pathlib import Path

import config
import utils


def main():
    parser = argparse.ArgumentParser(
        description="Merge multiple CSV files and remove duplicates"
    )
    parser.add_argument(
        'files',
        nargs='+',
        type=Path,
        help='CSV files to merge'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=config.OUTPUT_DIR / 'merged_resources.csv',
        help='Output file path (default: output/merged_resources.csv)'
    )
    parser.add_argument(
        '--no-dedupe',
        action='store_true',
        help='Skip deduplication step'
    )
    
    args = parser.parse_args()
    
    logger = utils.setup_logging("merge_csvs")
    
    logger.info("Starting CSV merge")
    logger.info("="*80)
    
    # Load all CSV files
    all_resources = []
    for csv_file in args.files:
        if not csv_file.exists():
            logger.error(f"File not found: {csv_file}")
            continue
        
        logger.info(f"Loading: {csv_file}")
        resources = utils.load_existing_resources(csv_file)
        logger.info(f"  Loaded {len(resources)} resources")
        all_resources.extend(resources)
    
    if not all_resources:
        logger.error("No resources loaded!")
        return 1
    
    logger.info(f"\nTotal resources loaded: {len(all_resources)}")
    
    # Deduplicate if requested
    if not args.no_dedupe:
        logger.info("\nDeduplicating...")
        all_resources = utils.deduplicate_resources(all_resources, logger)
    
    # Save merged file
    logger.info(f"\nSaving merged file to: {args.output}")
    utils.save_resources_to_csv(all_resources, args.output, logger)
    
    # Create summary report
    report_path = args.output.parent / f"{args.output.stem}_report.txt"
    utils.create_summary_report(all_resources, report_path, logger)
    
    logger.info("\n" + "="*80)
    logger.info("MERGE COMPLETE")
    logger.info("="*80)
    logger.info(f"Total resources in merged file: {len(all_resources)}")
    logger.info(f"Output: {args.output}")
    logger.info(f"Report: {report_path}")
    logger.info("="*80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

