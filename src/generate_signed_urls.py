import boto3
from botocore.client import Config
import sys
import json
import urllib.parse
import requests
from typing import List, Dict


def upsert_agency_to_database(agency_id: str, agency_name: str, data_url: str) -> bool:
    """
    Upsert agency data to mock_ckb table via Resql endpoint
    Try INSERT first, if it fails with conflict, then UPDATE
    """
    try:
        agency_data_hash = f"{agency_name}_hash"

        payload = {
            "agencyId": agency_id,
            "agencyDataHash": agency_data_hash,
            "dataUrl": data_url,
        }

        # Try INSERT first
        insert_url = "http://resql:8082/global-classifier/insert-agency-presigned-url"
        response = requests.post(insert_url, json=payload, timeout=30)

        if response.status_code == 200:
            print(f"Successfully inserted new agency {agency_id} to database")
            return True
        elif response.status_code == 400 and "duplicate key" in response.text.lower():
            # If INSERT fails due to duplicate key, try UPDATE
            print(f"Agency {agency_id} exists, updating...")

            update_url = (
                "http://resql:8082/global-classifier/update-agency-presigned-url"
            )
            update_response = requests.post(update_url, json=payload, timeout=30)

            if update_response.status_code == 200:
                print(f"Successfully updated agency {agency_id} in database")
                return True
            else:
                print(
                    f"Failed to update agency {agency_id}: HTTP {update_response.status_code}"
                )
                print(f"Response: {update_response.text}")
                return False
        else:
            print(f"Failed to insert agency {agency_id}: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print(f"Error upserting agency {agency_id} to database: {e}")
        return False


def main():
    print("Python script started...")

    # Check if agencies data is provided as command line argument
    if len(sys.argv) < 2:
        print('Usage: python generate_signed_urls.py "<url_encoded_agencies_json>"')
        print(
            "Expected format: URL-encoded JSON array with agencyId and agencyName fields"
        )
        sys.exit(1)

    try:
        # Decode the URL-encoded string first
        encoded_agencies = sys.argv[1]
        decoded_agencies_str = urllib.parse.unquote(encoded_agencies)

        # Parse JSON
        agencies = json.loads(decoded_agencies_str)
        print(f"Processing {len(agencies)} agencies")

    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse agencies JSON: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error during parsing: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    try:
        s3_client = boto3.client(
            "s3",
            endpoint_url="http://minio:9000",
            aws_access_key_id="minioadmin",
            aws_secret_access_key="minioadmin",
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
    except Exception as e:
        print(f"Error creating S3 client: {e}")
        sys.exit(1)

    # Build list of files to process from agencies
    files_to_process: List[Dict[str, str]] = []
    for agency in agencies:
        agency_name = agency.get("agencyName")
        agency_id = agency.get("agencyId")

        if agency_name:
            files_to_process.append(
                {
                    "bucket": "ckb",
                    "key": f"{agency_name}/{agency_name}.zip",
                    "agencyId": agency_id,
                }
            )
        else:
            print(f"Warning: Agency missing agencyName: {agency}")

    if not files_to_process:
        print("Error: No valid agencies found to process")
        sys.exit(1)

    # Generate presigned URLs
    presigned_urls: List[str] = []
    successful_agencies: List[Dict] = []

    print("Generating presigned URLs...")
    for file_info in files_to_process:
        try:
            url = s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": file_info["bucket"], "Key": file_info["key"]},
                ExpiresIn=24 * 3600,  # 24 hours in seconds
            )
            presigned_urls.append(url)
            successful_agencies.append(
                {
                    "agency_id": file_info.get("agencyId"),
                    "agency_name": file_info["key"].split("/")[
                        0
                    ],  # Extract agency name from key
                    "data_url": url,
                }
            )
        except Exception as e:
            print(f"Failed to generate URL for: {file_info['key']}")
            print(f"   Error: {str(e)}")

    print(f"Generated {len(presigned_urls)} URLs successfully")

    # Upsert agencies to database
    if successful_agencies:
        print("Storing agencies in database...")
        db_success_count = 0

        for agency_data in successful_agencies:
            success = upsert_agency_to_database(
                agency_data["agency_id"],
                agency_data["agency_name"],
                agency_data["data_url"],
            )
            if success:
                db_success_count += 1

        print(
            f"Successfully stored {db_success_count}/{len(successful_agencies)} agencies in database"
        )

    # Check if any URLs were generated
    if not presigned_urls:
        print("No URLs were generated successfully")
        sys.exit(1)

    print("Presigned URL generation completed successfully")


if __name__ == "__main__":
    main()
