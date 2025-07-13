#!/usr/bin/env python3
# filepath: c:\Users\charith.bimsara_root\Rootcode\Estonian-Gov-AI\New\Global-Classifier\src\s3_dataset_processor\download_source_dataset.py
"""
Direct Python script for downloading datasets from S3 signed URLs.
Replaces the FastAPI /download-datasets endpoint for CronManager execution.
"""

import sys
import json
import argparse
import logging
from pathlib import Path
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Add the s3_dataset_processor to Python path to import modules FIRST
# This path corresponds to the volume mount in docker-compose.yml
script_dir = Path("/app/src/s3_dataset_processor")
sys.path.insert(0, str(script_dir))

# Now import the services AFTER adding to path
try:
    from services.url_decoder_service import URLDecoderService
    from services.download_service import DownloadService
    from services.extraction_service import ExtractionService
    from handlers.response_handler import ResponseHandler

    logger.info("✅ Successfully imported all required modules")
except ImportError as e:
    logger.error(f"❌ Failed to import required modules: {e}")
    logger.error(f"Python path: {sys.path}")
    logger.error(f"Script directory exists: {script_dir.exists()}")
    if script_dir.exists():
        logger.error(f"Contents of script directory: {list(script_dir.iterdir())}")
    sys.exit(1)


def main():
    """Main function to handle dataset download process."""
    parser = argparse.ArgumentParser(
        description="Download datasets from S3 signed URLs"
    )
    parser.add_argument(
        "--encoded-data", required=True, help="Base64 encoded signed URLs data"
    )
    parser.add_argument(
        "--extract-files",
        action="store_true",
        default=True,
        help="Extract downloaded files",
    )
    parser.add_argument("--output-json", help="Output file path for results JSON")

    args = parser.parse_args()

    try:
        if not args.encoded_data or not isinstance(args.encoded_data, str):
            logger.error("'encoded_data' must be a non-empty string")
            sys.exit(1)

        logger.info("Initializing services...")
        # Initialize services
        url_decoder_service = URLDecoderService()
        download_service = DownloadService()
        extraction_service = ExtractionService()
        response_handler = ResponseHandler()

        logger.info("Decoding signed URLs...")
        # Decode the data using service
        decoded_data = url_decoder_service.decode_signed_urls(args.encoded_data)
        logger.info(f"Starting download for {len(decoded_data)} files")

        logger.info("Processing downloads...")
        # Process downloads using service
        downloaded_files, successful_downloads, failed_downloads = (
            download_service.process_downloads(decoded_data)
        )

        logger.info("Processing extractions...")
        # Process extractions using service
        extracted_folders = extraction_service.process_extractions(
            downloaded_files, args.extract_files
        )

        logger.info("Formatting response...")
        # Format response using handler
        response = response_handler.format_download_response(
            decoded_data,
            downloaded_files,
            successful_downloads,
            failed_downloads,
            extracted_folders,
        )

        # Output results
        if args.output_json:
            with open(args.output_json, "w") as f:
                json.dump(response.dict(), f, indent=2)
            logger.info(f"Results written to {args.output_json}")
        else:
            print(json.dumps(response.dict(), indent=2))

        # Log summary
        logger.info(
            f"Download completed: {successful_downloads} successful, {failed_downloads} failed"
        )
        logger.info(f"Extracted folders: {len(extracted_folders)}")

        # Exit with appropriate code
        sys.exit(0 if response.success else 1)

    except ValueError as e:
        logger.error(f"Decoding error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        logger.error(f"Internal error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
