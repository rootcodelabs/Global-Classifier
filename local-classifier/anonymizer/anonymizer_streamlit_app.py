import streamlit as st
import pandas as pd
import requests
from io import BytesIO

st.title("Data Anonymizer")

uploaded_file = st.file_uploader("Upload your Excel file", type="xlsx")

columns_to_anonymize = st.text_input("Enter the column names to anonymize (comma-separated)")

if st.button("Anonymize"):
    if uploaded_file is not None and columns_to_anonymize:
        file_data = BytesIO(uploaded_file.read())

        files = {'file': (uploaded_file.name, file_data, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        data = {'columns': columns_to_anonymize}

        response = requests.post("http://localhost:8010/anonymize-file", files=files, data=data)

        if response.status_code == 200:
            st.success("Anonymization successful! Download the file below:")
            st.download_button(label="Download Anonymized File", data=response.content, file_name=f"anonymized_{uploaded_file.name}")
        else:
            st.error(f"An error occurred: {response.text}")
    else:
        st.warning("Please upload a file and enter the column names.")
