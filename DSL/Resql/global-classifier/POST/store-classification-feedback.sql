INSERT INTO classification_feedback (
  chat_id,
  inference_id,
  actual_agency_id
)
VALUES (
  :chatId,
  :inferenceId,
  :actualAgencyId,
  :feedback_timestamp::timestamp
  )
RETURNING id, chat_id, inference_id, feedback_timestamp;