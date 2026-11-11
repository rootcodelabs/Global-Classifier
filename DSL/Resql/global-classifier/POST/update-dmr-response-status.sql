UPDATE public.dmr_incoming_messages
SET response_status       = :responseStatus,
    response_error        = NULLIF(:responseError, ''),
    response_attempts     = response_attempts + CASE WHEN :responseStatus = 'SKIPPED' THEN 0 ELSE 1 END,
    response_attempted_at = now(),
    responded_at          = CASE WHEN :responseStatus = 'SENT' THEN now() ELSE NULL END
WHERE message_id = :messageId::uuid
  AND (response_status IS NULL OR response_status = 'PENDING')
RETURNING message_id, response_status, response_attempts;
