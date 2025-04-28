const { Client } = require("@opensearch-project/opensearch");
const { openSearchConfig } = require("./config");

const client = new Client({
  node: openSearchConfig.getUrl(),
  ssl: openSearchConfig.ssl,
});

async function searchDatasetGroupNotification({
  sessionId,
  connectionId,
  sender,
}) {
  try {
    const response = await client.search({
      index: openSearchConfig.datasetGroupProgress,
      body: {
        query: {
          bool: {
            must: { match: { sessionId } },
          },
        },
        sort: { timestamp: { order: "desc" } },
        size: 1,
      },
    });
    for (const hit of response.body.hits.hits) {
      if (!hit._source.sentTo?.includes(connectionId)) {
        console.log(`hit: ${JSON.stringify(hit)}`);
        const sessionJson = {
          sessionId: hit._source.sessionId,
          progressPercentage: hit._source.progressPercentage,
          validationStatus: hit._source.validationStatus,
          validationMessage: hit._source.validationMessage,
        };
        await sender(sessionJson);
        await markAsSent(hit, connectionId);
      }
    }
  } catch (e) {
    console.error(e);
    await sender({});
  }
}

async function searchModelNotification({ sessionId, connectionId, sender }) {
  try {
    const response = await client.search({
      index: openSearchConfig.dataModelProgress,
      body: {
        query: {
          bool: {
            must: { match: { sessionId } },
          },
        },
        sort: { timestamp: { order: "desc" } },
        size: 1,
      },
    });

    for (const hit of response.body.hits.hits) {
      if (!hit._source.sentTo?.includes(connectionId)) {
        console.log(`hit: ${JSON.stringify(hit)}`);
        const sessionJson = {
          sessionId: hit._source.sessionId,
          progressPercentage: hit._source.progressPercentage,
          trainingStatus: hit._source.trainingStatus,
          trainingMessage: hit._source.trainingMessage,
        };
        await sender(sessionJson);
        await markAsSent(hit, connectionId);
      }
    }
  } catch (e) {
    console.error(e);
    await sender({});
  }
}

async function markAsSent({ _index, _id }, connectionId) {
  await client.update({
    index: _index,
    id: _id,
    retry_on_conflict: openSearchConfig.retry_on_conflict,
    body: {
      script: {
        source: `if (ctx._source.sentTo == null) {
          ctx._source.sentTo = [params.connectionId];
        } else {
          ctx._source.sentTo.add(params.connectionId);
        }`,
        lang: "painless",
        params: { connectionId },
      },
    },
  });
}

async function updateDatasetGroupProgress(
  sessionId,
  progressPercentage,
  validationStatus,
  validationMessage
) {
  await client.index({
    index: "dataset_progress_sessions",
    body: {
      sessionId,
      validationStatus,
      progressPercentage,
      validationMessage,
      timestamp: Date.now(),
    },
  });
}

async function updateModelProgress(
  sessionId,
  progressPercentage,
  trainingStatus,
  trainingMessage
) {
  await client.index({
    index: "data_model_progress_sessions",
    body: {
      sessionId,
      trainingStatus,
      progressPercentage,
      trainingMessage,
      timestamp: Date.now(),
    },
  });
}

module.exports = {
  searchDatasetGroupNotification,
  searchModelNotification,
  updateDatasetGroupProgress,
  updateModelProgress,
};