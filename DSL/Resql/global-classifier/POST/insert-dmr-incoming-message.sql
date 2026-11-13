INSERT INTO public.dmr_incoming_messages (message_id, sender_id, recipient_id, chat_id, chat_created_at, message_type, sent_at)
VALUES (
    :messageId::uuid,
    :senderId::uuid,
    NULLIF(:recipientId, '')::uuid,
    NULLIF(:chatId, '')::uuid,
    NULLIF(:chatCreatedAt, ''),
    NULLIF(:messageType, '')::dmr_message_type,
    NULLIF(:sentAt, '')::timestamptz
)
ON CONFLICT (message_id) DO NOTHING
RETURNING message_id, response_message_id;