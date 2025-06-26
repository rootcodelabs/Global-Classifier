# First-Time Agency Dataset Import Flow

## 1. Overview

This document describes the architectural flow for the first-time import and generation of a dataset for a new agency within the Global Classifier system. This process is initiated after an agency is recognized by the system and its data needs to be ingested from the Common Knowledge Base (CKB) and processed into a usable format for the classifier.

The primary orchestrator of this flow is the `/globalclassifier/POST/cronmanager/agency/data/generate` service, which coordinates data retrieval, metadata management, the dataset generation process, and storage.

## 2. Actors and Components Involved

*   **Global Classifier Cron Manager (`/globalclassifier/POST/cronmanager/agency/data/generate`)**: The central service that orchestrates the entire first-time dataset generation flow.
*   **Common Knowledge Base (CKB)**: The external system and source for raw agency data. It exposes data via S3 storage.
*   **CKB S3 Storage**: Stores the raw agency datasets.
    *   **CKB S3 Storage**: Stores the raw agency datasets.
*   **Global Classifier Storage**: Internal storage (e.g., S3 bucket) used by the Global Classifier to store downloaded raw data (temporarily) and the final processed datasets.
*   **Global Classifier ReSQL Database**: Stores metadata related to agencies, datasets, and their generation progress. Accessed via ReSQL endpoints.
    *   Key table: `GcIntegratedAgencies` (stores agency-specific information).
    *   Dataset metadata tables (for tracking status, location of data, etc.).
*   **Dataset Generator Service (`/dataset-generator/POST/cronmanager/dataset/generate`)**: A dedicated service responsible for taking the raw agency data and transforming it into the structured dataset required by the Global Classifier.
*   **Global Classifier SSE Service (`/globalclassifier/SSE/dataset-generation-progress`)**: Provides Server-Sent Events for real-time monitoring of the dataset generation progress, typically consumed by a UI.
*   **Integrate Agencies Main Interface**: A user interface or system entry point for managing agency integrations, which may lead to the initiation of this flow.

## 3. Detailed Flow Steps

The following steps outline the process for a first-time dataset import and generation for a specific agency:

### 3.1. Initiation

1.  **Trigger**: The `/globalclassifier/POST/cronmanager/agency/data/generate` cron job is initiated for a specific agency.
    *   *(Assumption: This is triggered for an agency that has been newly onboarded or marked as requiring its first dataset generation, likely following an action from the "Integrate Agencies Main Interface" or an automated detection of a new agency requiring data.)*

### 3.2. Data Retrieval from CKB

2.  **Obtain Secure Data URL**: The Cron Manager service interacts with CKB to obtain a pre-signed S3 URL for the specific agency's raw dataset. This URL provides secure, temporary access to the data.
3.  **Download Raw Data**: Using the obtained pre-signed S3 URL, the Cron Manager service downloads the raw agency data from the CKB S3 storage into the Global Classifier's environment.

### 3.3. Data Storage (Raw Data)

4.  **Store Raw Data Temporarily**: The downloaded raw agency data is uploaded to a temporary location within the Global Classifier's internal storage. This makes the data accessible for the subsequent generation process.

### 3.4. Metadata Management (Initial)

5.  **Create Initial Dataset Metadata**: The Cron Manager service calls a ReSQL endpoint (e.g., `/globalclassifier/resql/add-dataset-metadata`) to create an initial metadata record for this new dataset. This record typically includes:
    *   A unique dataset ID.
    *   Link to the `agency_id`.
    *   Initial status (e.g., "Pending Generation", "Data Retrieved").
    *   Timestamp of creation.
    *   Reference to the location of the raw data in Global Classifier storage.

### 3.5. Dataset Generation

6.  **Invoke Dataset Generator**: The Cron Manager service triggers the `/dataset-generator/POST/cronmanager/dataset/generate` service. It passes necessary information, such as the location of the raw data in GC storage and the dataset metadata ID.
7.  **Data Processing**: The Dataset Generator service performs the core data transformation:
    *   Reads the raw data.
    *   Cleans, preprocesses, and transforms the data into the required schema and format for the Global Classifier.
    *   During this process, it periodically updates the dataset's metadata record in the ReSQL database (e.g., via `/globalclassifier/resql/update-dataset-generation-progress`) with the current status (e.g., "Sync in progress with CKB" or "Sync completed").
    *   It also publishes these status updates to the `/globalclassifier/SSE/dataset-generation-progress` endpoint, allowing the dataset generator UI to monitor in real-time.
    *   It also publishes these progress updates to the `/globalclassifier/SSE/dataset-generation-progress` endpoint, allowing UIs or other services to monitor in real-time.

### 3.6. Data Storage (Processed Dataset)

8.  **Store Generated Dataset**: Upon successful completion of the generation process, the Dataset Generator service uploads the final, processed dataset to a designated location in the Global Classifier's internal storage.

### 3.7. Metadata Management (Final)

9.  **Finalize Dataset Metadata**: The dataset's metadata record in the ReSQL database is updated to reflect the completion of the generation process. 
 
### 3.8. Cleanup

10. **Delete Temporary Raw Data**: After the generated dataset is successfully stored and metadata is updated, the Cron Manager service deletes the temporary copy of the raw agency data that was downloaded from CKB and stored in the Global Classifier's environment.
    *   *(Assumption: This step refers to deleting the local copy within the Global Classifier's system, not the original data in CKB S3 storage.)*

## 4. Progress Monitoring

*   The status of the dataset generation can be tracked by querying the dataset metadata via ReSQL.
*   Real-time progress updates are available by subscribing to the `/globalclassifier/SSE/dataset-generation-progress` Server-Sent Events stream.

## 5. Key API Endpoints and Services Involved

*   **Orchestration**:
    *   `POST /globalclassifier/cronmanager/agency/data/generate`: Initiates and manages the first-time dataset generation for an agency.
*   **Data Source Interaction (CKB - Conceptual)**:
    *   Interaction to get a signed S3 URL for agency data (e.g., an internal CKB API or library).
    *   `GET /ckb/GET/agency/data/exists`: (Potentially a preliminary check before initiating the main flow) Checks if data for an agency exists in CKB.
*   **Dataset Generation**:
    *   `POST /dataset-generator/cronmanager/dataset/generate`: Triggers the actual processing of raw data into a usable dataset.
*   **Metadata Management (ReSQL)**:
    *   `POST /globalclassifier/resql/add-dataset-metadata`: Creates initial metadata for the dataset.
    *   `POST /globalclassifier/resql/update-dataset-generation-progress` (or similar): Updates the status and progress of dataset generation.
*   **Progress Monitoring (SSE)**:
    *   `GET /globalclassifier/SSE/dataset-generation-progress`: Provides a stream of real-time updates on generation progress.
*   **Agency Information (ReSQL/API)**:
    *   `GET /globalclassifier/GET/agencies`: Lists integrated agencies.
    *   `GET /globalclassifier/resql/get-integrated-agency`: Retrieves details for a specific integrated agency.

This flow ensures that data from new agencies is systematically imported, processed, and made available for the Global Classifier, with appropriate metadata tracking and progress visibility.
