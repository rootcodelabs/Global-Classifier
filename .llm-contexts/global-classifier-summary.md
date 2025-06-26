# Global Classifier: Detailed Outline

## Core Purpose and Vision

The Global Classifier is a central intelligent routing system within the overarching Bürokratt network. Its primary purpose is to accurately direct user inquiries that an initial agency-specific Bürokratt (chatbot) cannot resolve to the correct government agency or, if necessary, to a human agent.

### Vision:

- To act as a smart "switchboard" ensuring citizens' queries reach the most appropriate point of contact within the Estonian government's e-services network, even if the user initially contacts the "wrong" agency's chatbot.
- To improve the efficiency of the Bürokratt network by reducing misrouted queries and the need for manual re-direction.
- To enhance the user experience by providing a more seamless journey across different government services, making the network feel more like a single, unified entity.
- To continuously learn and improve its routing accuracy through feedback mechanisms.

## Key Actors & Workflow

(Based on the provided image and PRD)

- **End User:** Initiates a conversation with an agency-specific Bürokratt (e.g., BYK A - Police and Border Guard).
- **Agency-Specific Bürokratt (BYK A, BYK B, etc.):** The individual chatbot instance for a specific government agency.
    - Attempts to answer the user's query.
    - If BYK A cannot answer or determines the query is outside its scope, it escalates the conversation to the Global Classifier.
- **Global Classifier:**
    - Receives the escalated conversation (likely the conversation history or the specific problematic user inquiry).
    - Uses its trained ML model to classify the inquiry and determine the most relevant target government agency.
    - Crucially, it must also be able to determine if the inquiry does not fit any known agency (Out-of-Distribution / "Agency Undetected").
- **DMR (Distributed Message Rooms) / BYK Central Com:** (As per the image) This component seems to be the central communication hub.
    - If the Global Classifier identifies a target agency (e.g., Agency B) that has its own Bürokratt (BYK B), the Global Classifier likely informs the DMR (or a similar central routing mechanism) to forward the conversation/query to BYK B.
    - If the Global Classifier determines "Agency Undetected" or if the target agency has no Bürokratt, the query might be routed to a general human agent pool or a specific backoffice for manual handling (as per PRD, "calls another endpoint within the Buerokratt chatbot management interface which will let the human answer the question").
- **Bürokratt Backoffice / Agency Admins:**
    - Receive conversations routed to their agency.
    - Can report conversations misclassified by the Global Classifier as "irrelevant" to their agency.
- **Global Classifier Admins & Model Trainers:**
    - Manage users, agencies, and data sources.
    - Train, evaluate, and deploy classification models.
    - Review and re-classify "corrected conversations."

### Workflow Summary:

- User asks BYK A a question.
- BYK A cannot answer and escalates to Global Classifier (via a POST endpoint).
- Global Classifier analyzes the query and classifies it to:
    - Target Agency B: Informs DMR/Central Com to route to BYK B.
    - "Agency Undetected" / Human: Informs DMR/Central Com to route to a human agent/central backoffice.
- The conversation is handled by the new target (BYK B or human).
- Agency admins can flag misrouted conversations, which are sent back to the Global Classifier's "Corrected Conversations Module."
- Global Classifier trainers use this feedback to improve the model.

## Main Features & Modules

(Based on PRD and our discussions)

### Classification Core (Model Inference):

- **Function:** The heart of the system. Receives conversation data and uses a trained ML model (e.g., fine-tuned Gemma 2 9B) to predict the most appropriate government agency.
- **Input:** Conversation history/user query (JSON payload via a POST endpoint).
- **Output:** Predicted agency label (or "Agency Undetected") and potentially confidence scores.
- **Technical:** Deployed as an API endpoint, optimized for low latency (target <1000ms).

### "Agency Undetected" / Out-of-Distribution (OOD) Handling:

- **Function:** A critical capability to identify queries that do not clearly belong to any of the known/trained agency classes. Prevents misdirection and allows for appropriate fallback (e.g., to a general human agent).
- **Implementation:** Likely a hybrid approach:
    - Training the classifier with an explicit "Agency Undetected" class using diverse negative samples.
    - Applying softmax probability thresholding as a secondary check.

### Datasets Module:

- **Function:** Allows Admins/Trainers to manage data sources for training the classifier.
- **Features:**
    - Per-agency data source management (represented as "tiles" in the UI).
    - Supported data sources: Websites (URLs), information documents (PDF, DOCX, etc.), conversation text files, and textual descriptions of agency scope/services.
    - Indication of dataset deployment status (used for training or not).
    - Dataset versioning.
    - Ability to download generated/aggregated datasets.
    - Status indicators for synthetic data generation (e.g., "data generated," "generation in progress," "generation failed").
- **Backend:** Manages storage and processing of these diverse sources.

### Synthetic Conversation Generation Module:

- **Function:** Addresses the lack of readily available labeled training data by generating synthetic conversations.
- **Process:**
    - Uses a larger LLM (e.g., Gemma 2 9B/27B).
    - Takes unstructured content from the "Datasets Module" (agency websites, documents, descriptions) as input.
    - Uses zero-shot/few-shot prompting and prompt injection to generate realistic user-bot conversational snippets relevant to specific agencies, ending with a user query needing classification.
    - Generates examples for known agencies and for the "Agency Undetected" class.
- **Output:** Labeled conversational data suitable for training the classifier.

### Model Training & Versioning Module:

- **Function:** Enables Admins/Trainers to initiate and manage the training of new classifier models.
- **Features:**
    - Ability to select datasets/versions for training.
    - Initiate training jobs (potentially via a CronManager endpoint or UI trigger).
    - Track training progress (e.g., via SSE for UI progress bar).
    - Store training metrics and metadata (integrated with MLflow).
    - Version trained models (aligning with ADR VC-002).
    - Tag models as "outdated" if not trained on the current set of classes/agencies, preventing deployment of such models.
    - Display evaluation results (F1, Accuracy) for each model version.
    - Mechanism to push models to a testing environment and then to production.
- **Technical:** Involves ML pipelines for fine-tuning (e.g., Gemma 2 9B with PEFT/LoRA) and experiment tracking.

### Testing Module:

- **Function:** Provides an interface for Admins/Trainers to test deployed models.
- **Features:**
    - Select either the production model or a model in the test environment.
    - Input a user conversation (in the same structure the model expects during inference) to get a classification prediction.
    - Helps validate model behavior before full deployment or after updates.

### Corrected Conversations Module (Feedback Loop):

- **Function:** A crucial component for continuous improvement. Receives conversations flagged as "incorrectly classified" by government agency admins from their Bürokratt backoffice.
- **Process:**
    - Incorrectly routed conversations appear in a tabular format in the Global Classifier UI.
    - Triggers notifications (e.g., email) to Trainers/Admins.
    - Trainers review the conversation and re-classify it to the correct department/agency (or confirm "Agency Undetected").
    - The corrected, anonymized conversation is then added to the training dataset to improve future model versions.

### User Management Module:

- **Function:** Manages access to the Global Classifier's backoffice functionalities.
- **Implementation:** Leverages existing Bürokratt TIM/TARA for authentication.
- **Roles:**
    - **Administrator:** Full access, including user management, organization/agency management (adding agencies, their IP addresses for routing), and pushing models to production.
    - **Model Trainer:** Can create/manage training data, train models, push models to testing, and handle corrected conversations.

### Dashboard Module:

- **Function:** Provides statistical insights into the Global Classifier's performance and workload.
- **Metrics Displayed:**
    - Number of classified conversations.
    - Number of reported (misclassified) conversations.
    - Number of pending conversations needing human re-classification.
    - Last model accuracy in production (based on re-assignment rates).

## Technical Integration Points

- **Incoming Classification Requests:** A POST endpoint (e.g., `/api/v1/global-classifier/classify` managed via Ruuter) that individual Bürokratt instances call when escalating a conversation.
    - **Payload:** JSON containing conversation history/query.
- **Outgoing Routing Instructions:** After classification, the Global Classifier needs to communicate the routing decision. This likely involves calling an endpoint on the DMR or a central Bürokratt platform management interface.
    - **Payload:** JSON containing `conversation_id` and `target_agency_id` (or a special identifier for "human" / "undetected").
- **Feedback Loop Integration:** An endpoint (or mechanism) for the Global Classifier to receive "corrected conversation" data from the agency backoffices.
- **Common Knowledge Base (CKB) Integration:** An API or interface to pull unstructured documents, URLs, and other content for agencies to be used in synthetic data generation.
- **User Authentication:** Integration with TIM/TARA for securing its own backoffice/admin interface.
- **MLflow Integration:** For experiment tracking, model versioning, and metrics storage.
- **Ruuter:** Utilized for exposing its own API endpoints and potentially for orchestrating calls to other services.

## How It Will Be Used (By Persona)

- **End User:** Interacts indirectly. Experiences it as a more seamless transition if their query needs to be handled by a different part of the government network.
- **Agency-Specific Bürokratt Admin/CSA (Customer Support Agent):**
    - Receives queries correctly routed to their agency by the Global Classifier.
    - Uses their backoffice to flag conversations they believe were misrouted by the Global Classifier, triggering the feedback loop.
- **Global Classifier Administrator:**
    - Manages user access to the Global Classifier system.
    - Onboards new government agencies into the classifier (defines them as classes, adds their IP addresses/routing info).
    - Oversees the health and performance of the Global Classifier via the dashboard.
    - Has the final say on promoting tested models to the production environment.
- **Global Classifier Model Trainer:**
    - Manages data sources for each agency in the Datasets Module.
    - Initiates and monitors the synthetic data generation process.
    - Defines training runs, selects data, and trains new versions of the classification model.
    - Evaluates trained models using metrics and the Testing Module.
    - Promotes models to the testing environment.
    - Reviews conversations in the "Corrected Conversations Module," re-classifies them, and ensures they are incorporated into future training data.
    - Monitors model performance via the dashboard and MLflow.

This outline provides a comprehensive view of the Global Classifier, its intended functionality, and its role within the larger Bürokratt ecosystem.