const express = require("express");
const bodyParser = require("body-parser");
const verifySignature = require("./src/verifySignature.js");
const extractPayload = require("./src/extractPayload.js");
const axios = require("axios");
const helmet = require("helmet");

const app = express();
app.use(bodyParser.json());
app.use(helmet.hidePoweredBy());

app.post("/webhook", async (req, res) => {
  const isValid = verifySignature(req.body, req.headers);
  if (isValid) {
    const extractData = extractPayload(req.body);

    console.log("Response from extract data:", extractData);

    try {
      const response = await axios.post(process.env.RUUTER_PUBLIC_JIRA_URL, {
        payload: req.body,
        extractData: extractData,
      });

      console.log("Response from helper URL:", response.data);
      return res.status(200).send("Webhook processed and forwarded");
    } catch (error) {
      console.error("Error talking to helper URL:", error);
      return res.status(500).send("Error processing webhook");
    }
  } else {
    return res.status(400).send("Invalid signature");
  }
});

const PORT = process.env.PORT || 3008;
app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});
