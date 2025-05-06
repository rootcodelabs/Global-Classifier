INSERT INTO classification_feedback (
  chat_id,
  inference_id,
  actual_agency_id,
  predicted_agency_ids,
  is_predicted,
  feedback_notes,
  feedback_timestamp,
  metadata
)
VALUES (
  :chatId,
  :inferenceId,
  :actualAgencyId,
  :predictedAgencyIds::jsonb,
  :isPredicted,
  :feedback_notes,
  :feedback_timestamp::timestamp,
  :metadata::jsonb
)
RETURNING id, chat_id, inference_id, feedback_timestamp;