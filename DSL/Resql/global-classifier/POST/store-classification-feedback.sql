INSERT INTO classification_feedback (
  chat_id,
  inference_id,
  actual_agency_id,
  feedback_timestamp
)
VALUES (
  :chatId,
  :inferenceId,
  :actualAgencyId,
  :feedbackTimestamp::timestamp
  )
RETURNING id, chat_id, inference_id, feedback_timestamp;