"""Service for URL decoding operations."""

import urllib.parse
import json
from typing import List, Dict, Any


class URLDecoderService:
    """Service class for handling URL decoding operations."""

    @staticmethod
    def decode_signed_urls(encoded_data: str) -> List[Dict[str, Any]]:
        """
        Decode URL-encoded signed URLs data.

        Args:
            encoded_data: URL-encoded JSON string containing signed URLs

        Returns:
            List of decoded URL data dictionaries

        Raises:
            ValueError: If decoding or JSON parsing fails
        """
        try:
            # URL decode the data
            decoded_data = urllib.parse.unquote(encoded_data)

            # Parse JSON
            parsed_data = json.loads(decoded_data)

            return parsed_data

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON: {e}")

        except Exception as e:
            raise ValueError(f"Failed to decode data: {e}")
