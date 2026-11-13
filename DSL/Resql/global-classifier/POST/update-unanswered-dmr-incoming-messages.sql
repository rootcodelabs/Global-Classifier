UPDATE public.dmr_incoming_messages
SET response_attempted_at = now()
WHERE message_id IN (
    SELECT message_id
    FROM public.dmr_incoming_messages
    WHERE status IN ('CLASSIFIED', 'FAILED')
      AND (response_status IS NULL OR response_status = 'PENDING')
      AND COALESCE(response_attempted_at, processed_at) < now() - (:olderThanSeconds::integer * INTERVAL '1 second')
    ORDER BY processed_at
    LIMIT 50
    FOR UPDATE SKIP LOCKED
)
RETURNING message_id, response_message_id, sender_id, chat_id, chat_created_at, message_type,
          result_status, top_agency_id, top_agency_name, top_confidence, response_attempts;