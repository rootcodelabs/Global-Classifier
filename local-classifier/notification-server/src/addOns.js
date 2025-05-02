const { searchDatasetGroupNotification, searchModelNotification } = require("./openSearch");
const { serverConfig } = require("./config");

function buildDatasetGroupNotificationSearchInterval({
  sessionId,
  interval = serverConfig.refreshInterval,
}) {
  return ({ connectionId, sender }) => {
    const intervalHandle = setInterval(
      () =>
        searchDatasetGroupNotification({
          connectionId,
          sessionId,
          sender,
        }),
      interval
    );
    return () => clearInterval(intervalHandle);
  };
}

function buildModelNotificationSearchInterval({
  sessionId,
  interval = serverConfig.refreshInterval,
}) {
  return ({ connectionId, sender }) => {
    const intervalHandle = setInterval(
      () =>
        searchModelNotification({
          connectionId,
          sessionId,
          sender,
        }),
      interval
    );
    return () => clearInterval(intervalHandle);
  };
}

module.exports = {
  buildDatasetGroupNotificationSearchInterval,
  buildModelNotificationSearchInterval,
};
