import os
import json
import sys
from loguru import logger
import datetime
from typing import Dict, List, Any, Optional


# remove the default stderr handler
logger.remove()
# add stout handler
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")


class AgencyDataParser:
    """
    Parser for chunked agency data from JSON files.
    Processes each JSON file and outputs a corresponding text file.
    """

    def __init__(self, input_dir: str, output_dir: str):
        """
        Initialize the parser with input and output directories.

        Args:
            input_dir: Directory containing JSON files with chunked agency data
            output_dir: Directory where the output text files will be saved
        """
        self.input_dir = input_dir
        self.output_dir = output_dir

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logger.info(f"Created output directory: {output_dir}")

    def _parse_json_file(self, file_path: str) -> Optional[List[Dict[str, Any]]]:
        """
        Parse a JSON file and return its contents.

        Args:
            file_path: Path to the JSON file

        Returns:
            Parsed JSON data or None if an error occurs
        """
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
                logger.info(f"Successfully parsed JSON file: {file_path}")
                return data
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format in file: {file_path}")
        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {str(e)}")

        return None

    def _clean_content(self, content: str) -> str:
        """
        Clean the content by:
        1. Removing lines that have only one character
        2. Replacing multiple consecutive empty lines with a single empty line

        Args:
            content: The raw content string

        Returns:
            Cleaned content string
        """
        # Split content into lines
        lines = content.split("\n")

        # Filter out lines with only one character
        filtered_lines = [
            line for line in lines if len(line.strip()) > 1 or not line.strip()
        ]

        joined_content = "\n".join(filtered_lines)

        # Replace multiple consecutive empty lines with a single empty line
        import re

        cleaned_content = re.sub(r"\n\s*\n\s*\n+", "\n\n", joined_content)

        return cleaned_content.strip()

    def _extract_agency_info(
        self, data: List[Dict[str, Any]], file_name: str
    ) -> Dict[str, Any]:
        """
        Extract and structure agency information from parsed data into a standardized
        internal representation.

        Note: This internal structure should be replaced with the official structure
        defined in Task 1 when it becomes available.

        Args:
            data: Parsed JSON data containing agency information chunks
            file_name: Name of the source file for reference

        Returns:
            Standardized internal representation of agency information
        """
        # Define the standardized internal representation
        # This is a placeholder until the structure from Task 1 is available
        agency_data = {
            "title": "",  # Agency/document title
            "content": "",  # Full concatenated content
            "source_url": "",  # Original source URL
            "source_file": file_name,  # Source file name
            "metadata": {
                "description": "",  # Document description if available
                "chunk_count": 0,  # Number of chunks processed
                "processed_date": datetime.datetime.now().isoformat(),
            },
        }

        # Extract title, source_url, and description from the first chunk
        if data and len(data) > 0 and "content" in data[0]:
            first_chunk = data[0]["content"]
            agency_data["title"] = first_chunk.get("title", "")
            agency_data["source_url"] = first_chunk.get("source_url", "")
            agency_data["metadata"]["description"] = first_chunk.get("description", "")

        # Concatenate all content chunks
        content_text = ""
        chunk_count = 0

        for item in data:
            if "content" in item and "chunk" in item["content"]:
                content_text += item["content"]["chunk"] + "\n"
                chunk_count += 1

        # Clean the content
        cleaned_content = self._clean_content(content_text)

        agency_data["content"] = cleaned_content
        agency_data["metadata"]["chunk_count"] = chunk_count

        logger.debug(
            f"Created standardized internal representation with {chunk_count} chunks for {file_name}"
        )
        return agency_data

    def process_file(self, file_name: str) -> Optional[Dict[str, Any]]:
        """
        Process a single JSON file

        Args:
            file_name: Name of the JSON file

        Returns:
            Processed agency data or None if an error occurs
        """
        file_path = os.path.join(self.input_dir, file_name)

        data = self._parse_json_file(file_path)
        if not data:
            return None

        try:
            agency_data = self._extract_agency_info(data, file_name)
            logger.info(f"Successfully extracted agency information from {file_name}")
            return agency_data
        except Exception as e:
            logger.error(f"Error extracting agency info from {file_name}: {str(e)}")
            return None

    def save_to_text_file(self, agency_data: Dict[str, Any], file_name: str) -> bool:
        """
        Save agency data to an individual text file.

        Args:
            agency_data: Structured agency data (in standardized internal representation)
            file_name: Name of the JSON file (used to derive output file name)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate output file name (replacing extension)
            output_file_name = os.path.splitext(file_name)[0] + ".txt"
            output_path = os.path.join(self.output_dir, output_file_name)

            with open(output_path, "w", encoding="utf-8") as file:
                # Write title
                file.write(f"# {agency_data['title']}\n\n")

                # Write content
                file.write(agency_data["content"])

            logger.info(f"Successfully saved agency data to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving agency data: {str(e)}")
            return False

    def process_directory(self) -> int:
        """
        Process all JSON files in the input directory and create individual text files.

        Returns:
            Number of successfully processed files
        """
        success_count = 0

        try:
            # Get all JSON files in the input directory
            json_files = [
                f
                for f in os.listdir(self.input_dir)
                if f.endswith(".json") or f.endswith(".txt")
            ]

            if not json_files:
                logger.warning(f"No JSON files found in {self.input_dir}")
                return 0

            logger.info(f"Found {len(json_files)} files to process")

            # Process each file and create an individual output file
            for file_name in json_files:
                logger.info(f"Processing file: {file_name}")

                # Get agency data
                agency_data = self.process_file(file_name)
                if not agency_data:
                    continue

                # Save to individual text file
                if self.save_to_text_file(agency_data, file_name):
                    success_count += 1

            logger.info(
                f"Successfully processed {success_count} out of {len(json_files)} files"
            )

        except Exception as e:
            logger.error(f"Error processing directory {self.input_dir}: {str(e)}")

        return success_count


def main():
    # Define the data directories, input_dir is where the agencies JSON files are located and output_dir is where the output files will be saved
    input_dir = (
        "data/Tarbijakaitse_ja_Tehnilise_Jarelevalve_Amet"  # Directory with JSON files
    )
    output_dir = "data/output_Tarbijakaitse_ja_Tehnilise_Jarelevalve_Amet"  # Directory for output text files
    # input_dir = "data/ID.ee"
    # output_dir = "data/output_ID.ee"
    # input_dir = "data/Politsei-_ja_Piirivalveamet"
    # output_dir = "data/output_Politsei-_ja_Piirivalveamet"
    parser = AgencyDataParser(input_dir, output_dir)

    processed_count = parser.process_directory()

    logger.info(f"Processed {processed_count} agency files.")
    logger.info(f"Output files saved to {output_dir}")
    logger.info("Check logs for details.")


if __name__ == "__main__":
    main()
