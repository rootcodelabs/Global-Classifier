function extractPayload(payload) {
  const issueFields = payload.issue.fields;

  const title = issueFields.summary;

  const description = issueFields.description
    ? issueFields.description.replace(/\n/g, " ").replace(/\+\s*/g, "")
    : "";

  const attachments = issueFields.attachment.map((att) => att.filename);

  return {
    title: title,
    description: description,
    attachments: attachments,
  };
}

module.exports = extractPayload;
