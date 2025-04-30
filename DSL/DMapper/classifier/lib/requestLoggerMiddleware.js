/**
 * @param res Original Response Object
 * @param send Original UNMODIFIED res.send function
 * @return A patched res.send which takes the send content, binds it to contentBody on
 * the res and then calls the original res.send after restoring it
 */
const resDotSendInterceptor = (res, send) => (content) => {
  res.contentBody = content;
  res.send = send;
  res.send(content);
};

export const requestLoggerMiddleware =
  ({ logger }) =>
  (req, res, next) => {
    logger(
      `Request: {method: ${req.method}, url: ${
        req.url
      }, params: ${JSON.stringify(req.params)}, query: ${JSON.stringify(
        req.query
      )}, body: ${JSON.stringify(req.body)}`
    );
    res.send = resDotSendInterceptor(res, res.send);
    res.on("finish", () => {
      logger(
        `Response: {statusCode: ${res.statusCode}, responseData: ${res.contentBody}}`
      );
    });
    next();
  };
