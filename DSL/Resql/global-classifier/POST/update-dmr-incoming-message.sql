UPDATE public.dmr_incoming_messages
SET status          = :status::dmr_message_status,
    error_reason    = NULLIF(:errorReason, ''),
    sender_known    = :senderKnown::boolean,
    result_status   = NULLIF(:resultStatus, '')::dmr_result_status,
    top_agency_id   = NULLIF(:topAgencyId, '')::uuid,
    top_agency_name = NULLIF(:topAgencyName, ''),
    top_confidence  = NULLIF(:topConfidence, '')::numeric,
    classification  = NULLIF(:classification, '')::jsonb,
    processed_at    = now()
WHERE message_id = :messageId::uuid
  AND status = 'RECEIVED'
RETURNING message_id;