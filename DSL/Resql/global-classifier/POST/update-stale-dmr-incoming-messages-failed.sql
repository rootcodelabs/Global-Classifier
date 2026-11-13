UPDATE public.dmr_incoming_messages
SET status        = 'FAILED',
    error_reason  = 'processing interrupted',
    result_status = 'failed',
    processed_at  = now()
WHERE status = 'RECEIVED'
  AND received_at < now() - (:olderThanSeconds::integer * INTERVAL '1 second')
RETURNING message_id, response_message_id, sender_id, chat_id, chat_created, message_type;