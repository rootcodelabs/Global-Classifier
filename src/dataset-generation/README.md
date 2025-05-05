### Data Source Ingestion Script

This tool processes JSON files containing chunked text data about agencies and creates unified text document for each JSON file. It's designed to standardize the ingested content into a consistent internal Python object representation before writing to the output file.


## Usage

1. Install the required packages from the `requirements.txt` file.
2. Place your agency JSON files in the input directory
3. Run the script:
```bash
python data_source_ingestion.py
```

3. Find the output in the defined output directory

## Configuration

You can modify the input/output paths in the `main()` function of `data_source_ingestion.py`:

```python
input_dir = "data/Tarbijakaitse_ja_Tehnilise_Jarelevalve_Amet"  # Directory with JSON files
output_dir = "data/output_Tarbijakaitse_ja_Tehnilise_Jarelevalve_Amet"  # Directory for output
output_filename = "output.txt"  # Name of the output file
```

## Input Format

The script expects JSON files with content in the following structure:

```json
[
    {
        "content": {
            "chunk": "Text content from the agency...",
            "title": "Agency Title",
            "description": "Description of the agency",
            "source_url": "https://example.com/source"
        }
    },
    ...
]
```

## Output Format

The output is a text files containing agency information, with titles preserved.

