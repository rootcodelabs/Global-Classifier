
---

**NOTE** - The entire purpose of this copy of the local classifier project is to easily re-use components from the local classifier that are needed in the global classifier. This folder will be deleted once the global classifier repository matures. If you would like to use the local classifier please use the latest version from the "dev" branch [here](https://github.com/buerokratt/Classifier)

---

# Classifier


The classifier is an open-source model training platform which can be integrated with JIRA and Outlook to deploy custom classification models to classify and label incoming emails or JIRA tickets.

# Scope

This repo will primarily contain:


1. Architecture and other documentation (under the docs folder);
2. Docker Compose file to set up and run Classifier as a fully functional service;
3. You can view the UI designs for this project in this [Figma file](https://www.figma.com/design/VWoZu2s7auo7YTw49RqNtV/Estonian-Classifier-English-Version?node-id=712-1695&t=cx6ZZVuEkfWqlbZB-1)


## Dev setup

- Clone [Ruuter](https://github.com/buerokratt/Ruuter)
- Navigate to Ruuter and build the image using the command `docker build -t ruuter .`
- Clone [Resql](https://github.com/buerokratt/Resql)
- Navigate to Resql and build the image `docker build -t resql .`
- Clone [Data Mapper](https://github.com/buerokratt/DataMapper)
- Navigate to Data Mapper and build the image using the command `docker build -t data-mapper .`
- Clone [TIM](https://github.com/buerokratt/TIM)
- Navigate to TIM and build the image using the command `docker build -t tim .`
- Clone [Authentication Layer](https://github.com/buerokratt/Authentication-layer)
- Navigate to Authentication Layer, checkout to the `dev` branch and build the image using the command `docker build -f Dockerfile.dev -t authentication-layer .`
- Clone [S3 Ferry](https://github.com/buerokratt/S3-Ferry)
- Navigate to S3-Ferry and build the image using the command `docker build  -t s3-ferry .`
- Clone [Cron Manager](https://github.com/rootcodelabs/CronManager) (<i>This is a forked repo of the original Buerokratt CronManager with a Python environment included</i>)
- Navigate to Cron Manager `dev` branch and build the cron-manager-python image using the command `docker build -f Dockerfile.python -t cron-manager-python .`
- Replace the existing values in the Cron Manager config.ini file with the corresponding values for `OUTLOOK_CLIENT_ID` and `OUTLOOK_SECRET_KEY`. The following sections describe how these keys can be acquired.

## Give execution permission for all mounted shell scripts
- Navigate to the parent folder of the classifier project and run the below command to make the shell files executable

   `find classifier -type f -name "*.sh" -exec chmod +x {} \;`

### Setting up Microsoft Outlook Integration

1. **Sign in to Azure Portal**
    - Navigate to [Azure Portal](https://portal.azure.com) and log in.
    - Click on **Manage Microsoft Entra ID**.
![1](https://github.com/user-attachments/assets/abd47d5c-65ab-47b8-a0a7-dd7199055ac2)

2. **App Registration**
    - In the left-hand side menu, under the **Manage** section, select **App Registration**.
    - Click on the **New registration** button.
      ![3](https://github.com/user-attachments/assets/5be4b8b4-f2c7-459a-965b-96239d5e884a)
    - Provide a **Name** and select the **Account type** as required.
    - In the **Redirect URI** section, select **Web** and enter the callback URL of the Outlook consent app. 
      If deployed locally, the callback URL will be `http://localhost:3003/callback`. Please note that if you have deployed on another host other than localhost this should be `http://<base_url>/callback`.
![4](https://github.com/user-attachments/assets/1e246ca8-c37d-4fd1-93b6-61946cb0c9be)

3. **Copy OUTLOOK_CLIENT_ID**
    - After registering, you can find the **Application (Client) ID** which will serve as the **OUTLOOK_CLIENT_ID**. 
    - Copy this value and replace it in both the `constants.ini` file and the `DSL/CronManager/config/config.ini` file.

4. **Add Client Secret**
    - On the same page, navigate to the **Client credentials** section and click on **Add a certificate or secret**.
      ![5](https://github.com/user-attachments/assets/59a07937-db39-471c-9c32-d1091a8dc91b)
      
    - Select **Client secrets** and click on **New Client secret**. Provide a description and select an expiration time.
    - Once created, copy the **Value** field, which will serve as the **OUTLOOK_SECRET_KEY**. 
    - Add this value to the `constants.ini` file.
![7](https://github.com/user-attachments/assets/f2652f83-82ed-4013-a163-45143193bb91)

5. **Acquire OUTLOOK_REFRESH_KEY**
    - Navigate to the `outlook-consent-app` folder.
    - Set up the environment variables in the `.env` file as follows:
      ```
      NEXT_PUBLIC_CLIENT_ID=<OUTLOOK_CLIENT_ID>
      CLIENT_SECRET=<OUTLOOK_SECRET_KEY>
      REDIRECT_URI=http://localhost:3003/callback or http://<base_url>/callback 
      ```
    - if you deployed somewhare other than localhost, Redirect URI should be the url that you have provided to the **Redirect URI** section when you are registering the application.
    - Build and run the image using the command:
      ```bash
      docker compose up -d
      ```
    - Open `http://localhost:3003` or relevent url of the host in your browser and log into your Outlook account.
    - After logging in, you will be redirected to a page with text box and value in the text box will be your **OUTLOOK_REFRESH_KEY**.
    - Add this value to the `constants.ini` file and the `DSL/CronManager/config/config.ini` files.


### Jira Setup

1. **Generate API Token:**
   - Navigate to [Atlassian Profile](https://id.atlassian.com/manage-profile) and log in with your Jira credentials.
   - Click on the **Security** tab.
   - Scroll down to the **API Token** section, and click on `Create and manage API tokens`.
   - Click on **Create API Token** to generate a new token. **This token will serve as your `JIRA_API_TOKEN`.** Make sure to store it securely as it will be used later.

2. **Create Jira Webhook:**
   - Navigate to your **Jira Account** (This is where Jira issues will be created and predicted).
   - Go to **Settings → System → WebHooks**.
   - Click `Create WebHook` and configure it as follows:
     - **URL**: `Base_URL/webhook` (Replace `Base_URL` with the actual URL of your `jira-verification` container deployed in your infrastructure).
     - Under Events, select the checkboxes for `Issue Created` and `Issue Updated` to trigger the webhook upon these actions.
     - **Webhook Secret**: After creating the webhook, you will receive a `JIRA_WEBHOOK_SECRET`. **Save this secret as you will need to add it to your configuration files.**

3. **Set Values in `constants.ini`:**
   - Add the following values in your `constants.ini` file:
     - `JIRA_API_TOKEN` – The API token generated in step 1.
     - `JIRA_USERNAME` – Your Jira username. To find your Jira username, navigate to your profile in Jira, and it will be displayed under your account information.
     - `JIRA_CLOUD_DOMAIN` – The domain URL of your Jira cloud instance (e.g., `https://example.atlassian.net`).
     - `JIRA_WEBHOOK_ID` – You can retrieve this using steps provided under Retrievening Jira Webhook ID.
     - `JIRA_WEBHOOK_SECRET` – Jira webhook secret you got in **Create Jira Webhook** step.

4. **Create a `.env` file for Jira Configuration:**
   - Create a `.env` file in the folder called `jira-verification` and add the following:
     ```env
     JIRA_WEBHOOK_SECRET=<<JIRA_WEBHOOK_SECRET>>
     ```

### Retrieving Jira Webhook ID

To get the `JIRA_WEBHOOK_ID`, use the following CURL request with your Jira email and API token:

```bash
curl -X GET -u your-email@example.com:your-api-token -H "Content-Type: application/json" https://<JIRA_CLOUD_DOMAIN>/rest/webhooks/1.0/webhook
```

In the response, the webhook ID can be found in the `self` attribute. For example:

```json
"self": "https://example.net/rest/webhooks/1.0/webhook/1"
```

In this case, the `JIRA_WEBHOOK_ID` is `1`.

### Configuration for `config.env`

This file contains environment variables that are necessary for the operation of the application. Below is an explanation of each value, with a focus on obtaining the AWS S3-related values.

#### S3 Configuration Variables

1. **S3_REGION**:
   - This is the AWS region where your S3 bucket is located. For example, `eu-west-1` is the region for Ireland.
   - To find your S3 region:
     - Log in to your AWS Management Console.
     - Navigate to **S3**.
     - Look at the top-right corner of the S3 dashboard to see your region (e.g., `eu-west-1`, `us-east-1`).

2. **S3_ENDPOINT_URL**:
   - This is the endpoint URL for your S3 bucket in the specified region.
   - You can find this by:
     - Navigating to your S3 bucket.
     - AWS provides the region-specific endpoint. For example, for the `eu-west-1` region, the endpoint is `https://s3.eu-west-1.amazonaws.com`.

3. **S3_DATA_BUCKET_NAME**:
   - This is the name of the S3 bucket where your data will be stored.
   - To find or create your S3 bucket:
     - Go to the AWS **S3** dashboard.
     - If you already have a bucket, use its name.
     - To create a new bucket, click on **Create Bucket**, name it (e.g., `esclassifier-test`), and configure its settings.

4. **S3_DATA_BUCKET_PATH**:
   - This specifies the path within your S3 bucket where data will be stored. In this example, it's `data/`.
   - You can customize the directory structure within your bucket as per your project needs.

5. **S3_ACCESS_KEY_ID** and **S3_SECRET_ACCESS_KEY**:
   - These are the AWS access keys used to authenticate and authorize access to your S3 bucket.
   - To generate these keys:
     - Navigate to the **IAM** (Identity and Access Management) section in AWS.
     - Create a new user (or use an existing one) with **Programmatic Access** enabled.
     - Attach a policy that grants S3 permissions (such as `AmazonS3FullAccess` or a custom policy).
     - After creating the user, AWS will provide an **Access Key ID** and **Secret Access Key**. Store these values securely.

#### Local File System Path

6. **FS_DATA_DIRECTORY_PATH**:
   - This is the directory path on the local file system where data will be stored. Usually, this value is set to `/shared`.
   - It is useful for storing files locally in addition to, or instead of, uploading them to S3.

#### Other Configuration Variables

7. **API_CORS_ORIGIN**:
   - The value `*` means that the API allows requests from any domain (cross-origin resource sharing is fully open). This is useful during development but should be restricted to specific domains in production for security reasons.

8. **API_DOCUMENTATION_ENABLED**:
   - When set to `true`, this enables automatic generation of API documentation, such as Swagger or Redoc. This is helpful for developers to interact with and understand the API’s endpoints.

Ensure that your AWS credentials (S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY) are stored securely and never exposed publicly. It's recommended to use services like AWS Secrets Manager for production environments.

##### Ruuter Internal Requests

- When running ruuter either on local or in an environment make sure to adjust `- application.internalRequests.allowedIPs=127.0.0.1,{YOUR_IPS}` under ruuter environments

### Database setup

- For the initial setup of the database, run helper script `./token.sh`
- Provide the password for the database in constant.ini under the key `DB_PASSWORD`
- Run migrations added in this repository by running the helper script `./migrate.sh`(consider db properties before running the script)
- When creating new migrations, run `create-migration` script with parameters ` example : ./create-migration.sh <name-of-migration> <format>`
- This will create a new file in the respective directory and add the required headers, pass file name(ex: `data-model-sessions`) and the format(`sql` or `xml`) as inputs

### Open Search

- To Initialize Open Search run `./deploy-opensearch.sh <URL> <AUTH> <Is Mock Allowed - Default false>`
- To Use Opensearch locally run `./deploy-opensearch.sh http://localhost:9200 admin:admin true`

### Running the Final Docker Environment

This section explains how to run the Docker Compose file that starts the application. You have the option to run the application on either **CPU** or **GPU**, depending on your resources. Note that using a GPU will significantly speed up processing tasks such as model training and inference.

1. **To Run with CPU:**
   - Navigate to the root directory of the project.
   - Run the following command to build and start the Docker containers:
     ```bash
     docker compose up --build -d
     ```
   - This will start all necessary containers for the classifier service on your CPU.

2. **To Run with GPU:**
   - Ensure that CUDA is installed and your system has GPU support.
   - Navigate to the root directory of the project.
   - Run the following command to start the service with GPU support:
     ```bash
     docker compose -f docker-compose.gpu.yml up --build -d
     ```
   - This command will start the `data-enrichment`, `model-trainer`, and `model-inference` containers to utilize the GPU.

**Note:**
- In some environments, you may need to use `docker-compose` instead of `docker compose`, depending on your installation and version of Docker.
- Some containers, such as `tim`, `authentication-layer`, `dataset-enrichment`, and etc. may take longer to start and complete their initialization. The startup time will depend on your system’s processing power and internet connection speed.

By following these steps, you will have a fully functional service ready for use either on your local machine or in a server environment.

## Ngrok setup for local testing
To setup JIRA and Outlook integrations locally you need an https URL as a webhook. Since localhost by default http JIRA and Outlook APIs wouldn't be able to call your webhook endpoint if it's in localhost. You can overcome this by creating a ngrok tunnel to your localhost ports 3008 (JIRA Integration) and 8086 (Outlook Integration). And then provide the https URLs you receive from ngrok as webhook callback endpoints in JIRA and Outlook configurations
