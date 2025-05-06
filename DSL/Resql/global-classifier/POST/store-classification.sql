INSERT INTO classification_results (
  chat_id,
  inference_id,
  target_agencies,
  classification_timestamp
)
VALUES (
  :chatId,
  :inferenceId,
  :targetAgencies::jsonb,
  CURRENT_TIMESTAMP
)
RETURNING id, chat_id, inference_id, classification_timestamp;