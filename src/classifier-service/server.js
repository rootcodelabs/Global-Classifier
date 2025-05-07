// This is a simple Node.js logger service that mocks the classification of incoming conversations.

const express = require("express");
const app = express();
const port = 8090;

app.use(express.json());

app.post("/incoming-conversation", (req, res) => {
  console.log("Received classification request:");
  console.log(JSON.stringify(req.body, null, 2));

  // Simple mock response when classifier is unable to classify the chat
  // In a real-world scenario, this would be replaced with actual classification logic
  
  if (req.body.authorId === "1234") {
    return res.json({
      message: "unable to classify chat",
      operationSuccessful: false,
      statusCode: 400,
    });
  } else {
    res.json({
      predictedAgencies: [
        { burokrattId: "2544", confidence: 0.8 },
        { burokrattId: "2824", confidence: 0.6 },
        { burokrattId: "2713", confidence: 0.2 },
      ],
      message: "chat classified successfully",
      operationSuccessful: true,
      statusCode: 200,
    });
  }
});

app.listen(port, () => {
  console.log(`Classifier service listening at http://localhost:${port}`);
});
