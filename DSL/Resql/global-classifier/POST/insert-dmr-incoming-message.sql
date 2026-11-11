INSERT INTO public.dmr_incoming_messages (message_id, sender_id, recipient_id, chat_id, chat_created, message_type, sent_at)
VALUES (
    :messageId::uuid,
    :senderId,
    NULLIF(:recipientId, ''),
    NULLIF(:chatId, ''),
    NULLIF(:chatCreated, ''),
    NULLIF(:messageType, ''),
    NULLIF(:sentAt, '')::timestamptz
)
ON CONFLICT (message_id) DO NOTHING
RETURNING id, response_message_id;
