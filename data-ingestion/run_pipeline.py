#!/usr/bin/env python3
"""
Main pipeline orchestrator - runs the complete data ingestion pipeline.

This script runs both discovery and extraction steps in sequence.
"""

import sys
import subprocess
from pathlib import Path

import config
import utils


def run_step(script_name: str, logger) -> int:
    """
    Run a pipeline step (subprocess).
    
    Args:
        script_name: Name of the script to run
        logger: Logger instance
    
    Returns:
        Exit code from the script
    """
    script_path = config.SCRIPTS_DIR / script_name
    
    if not script_path.exists():
        logger.error(f"Script not found: {script_path}")
        return 1
    
    logger.info(f"\n{'='*80}")
    logger.info(f"Running: {script_name}")
    logger.info(f"{'='*80}\n")
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=config.BASE_DIR,
            check=False
        )
        
        if result.returncode != 0:
            logger.error(f"{script_name} failed with exit code {result.returncode}")
            return result.returncode
        
        logger.info(f"\n✓ {script_name} completed successfully")
        return 0
    
    except Exception as e:
        logger.error(f"Error running {script_name}: {e}")
        return 1


def main():
    """Main execution function."""
    logger = utils.setup_logging("pipeline")
    
    print("\n" + "="*80)
    print("DATA INGESTION PIPELINE")
    print("="*80)
    print("\nThis pipeline will:")
    print("  1. Discover organizations using Google Places API")
    print("  2. Scrape websites and extract data using OpenAI")
    print("  3. Generate CSV files ready for S3 upload")
    print("\n" + "="*80)
    
    # Validate configuration
    if not config.validate_config():
        logger.error("\nConfiguration validation failed!")
        logger.error("Please set up your API keys in a .env file")
        return 1
    
    logger.info("Configuration validated ✓")
    
    # Ask user to confirm
    response = input("\nReady to start pipeline? This will make API calls. (y/n): ").strip().lower()
    if response != 'y':
        logger.info("Pipeline cancelled by user")
        return 0
    
    # Step 1: Discover organizations
    logger.info("\n" + "="*80)
    logger.info("STEP 1: DISCOVER ORGANIZATIONS")
    logger.info("="*80)
    
    exit_code = run_step("1_discover_organizations.py", logger)
    if exit_code != 0:
        logger.error("Discovery step failed!")
        return exit_code
    
    # Step 2: Scrape and extract
    logger.info("\n" + "="*80)
    logger.info("STEP 2: SCRAPE AND EXTRACT")
    logger.info("="*80)
    
    exit_code = run_step("2_scrape_and_extract.py", logger)
    if exit_code != 0:
        logger.error("Extraction step failed!")
        return exit_code
    
    # Pipeline complete
    logger.info("\n" + "="*80)
    logger.info("PIPELINE COMPLETE! 🎉")
    logger.info("="*80)
    logger.info("\nYour CSV files are ready in the 'output' directory.")
    logger.info("Review the results, spot-check entries, and upload to S3.")
    logger.info("\nRecommended next steps:")
    logger.info("  1. Open the latest CSV in output/")
    logger.info("  2. Spot-check 10-20 entries for accuracy")
    logger.info("  3. Manually fix any issues")
    logger.info("  4. Merge with existing data if needed")
    logger.info("  5. Upload to S3")
    logger.info("="*80 + "\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

