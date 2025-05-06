
# Syntactic Data Generator

This Streamlit app allows users to upload an Excel file, select specific columns, and generate syntactic data using paraphrasing. The app uses an API to process the text and provides an option to download the newly generated data.

## Prerequisites

1. **Python packages**:  
   Ensure you have all the required Python packages installed. You can install them by running the following command in the app directory:

   ```bash
   pip install -r enrichment_streamlit_app_requirements.txt
   ```

2. **API Setup**:  
   This app interacts with an external API to process the text. You need to have the `data-enrichment-api` container running. This container is part of the classifier system. Please ensure that it is up and running before you start the Streamlit app.

   The app expects the API to be running at `http://localhost:8005/paraphrase`.

## How to Run the App

3. **Run the Streamlit app**:

   ```bash
   streamlit run streamlit_app.py
   ```

## Features

- Upload an Excel file (.xlsx format).
- Select columns to generate syntactic data using paraphrasing.
- Download the synthesized data in Excel format.

## Notes

- Ensure that the API used for paraphrasing (`data-enrichment-api`) is properly running and accessible at the specified URL.

---