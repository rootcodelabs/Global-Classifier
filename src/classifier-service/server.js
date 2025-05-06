// Node.js classifier service (simple logger version)
const express = require("express");
const app = express();
const port = 8090;

app.use(express.json());

app.post("/incoming-conversation", (req, res) => {
  console.log("Received classification request:");
  console.log(JSON.stringify(req.body, null, 2));

  // Simple mock response
  if(req.body.botId === "1234") {
    return res.json({
      message: "unable to classify chat",
      operationSuccessful: false,
      statusCode: 400,
    });
  }else{
    res.json({
      suggestedBots: [
        { botId: "2544", confidence: 0.8 },
        { botId: "2824", confidence: 0.6 }
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
