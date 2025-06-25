import boto3
from botocore.client import Config

# Create S3 client for MinIO
s3_client = boto3.client(
    's3',
    endpoint_url='http://minio:9000',  # Replace with your MinIO URL
    aws_access_key_id='minioadmin',        # Replace with your access key
    aws_secret_access_key='minioadmin',    # Replace with your secret key
    config=Config(signature_version='s3v4'),  # Hardcoded signature version
    region_name='us-east-1'  # MinIO usually works with any region
)

# List of files to generate URLs for
files_to_process = [
    {'bucket': 'ckb', 'key': 'agencies/Politsei-_ja_Piirivalveamet/Politsei-_ja_Piirivalveamet.zip'},
    {'bucket': 'ckb', 'key': 'agencies/ID.ee/ID.zip'},
    # Add more files as needed
    # {'bucket': 'ckb', 'key': 'agencies/another-agency/file.zip'},
]

# Generate presigned URLs
presigned_urls = []

print("Generating presigned URLs...")
for file_info in files_to_process:
    try:
        url = s3_client.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': file_info['bucket'], 'Key': file_info['key']},
            ExpiresIn=24 * 3600  # 4 hours in seconds
        )
        presigned_urls.append(url)
        print(f"✅ Generated URL for: {file_info['key']}")
        print(f"   URL: {url}")
    except Exception as e:
        print(f"❌ Failed to generate URL for: {file_info['key']}")
        print(f"   Error: {str(e)}")

output_file = 'minio_presigned_urls.txt'

try:
    with open(output_file, 'w') as f:
        # Write URLs separated by ||| delimiter (for your script)
        url_string = '|||'.join(presigned_urls)
        f.write(url_string)
        f.write('\n\n')
        
        # Also write each URL on separate lines for readability
        f.write("Individual URLs:\n")
        f.write("=" * 50 + "\n")
        for i, url in enumerate(presigned_urls, 1):
            f.write(f"URL {i}:\n{url}\n\n")
    
    print(f"\n✅ Presigned URLs saved to: {output_file}")
    print(f"Total URLs generated: {len(presigned_urls)}")
    
    # Display the combined URL string for easy copying
    if presigned_urls:
        print("\nCombined URL string (for signedUrls environment variable):")
        print("=" * 60)
        print('|||'.join(presigned_urls))
        
except Exception as e:
    print(f"❌ Failed to save URLs to file: {str(e)}")