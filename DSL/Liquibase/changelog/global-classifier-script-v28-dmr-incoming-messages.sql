-- liquibase formatted sql

-- changeset Oshan Nanayakkara:global-classifier-dmr-incoming-messages-enums
-- DMR envelope type. ChatMessage is the only type DMR has; any other type is stored as NULL and rejected.
CREATE TYPE dmr_message_type AS ENUM ('ChatMessage');
-- Processing of the incoming message: RECEIVED until it is classified, rejected or failed.
CREATE TYPE dmr_message_status AS ENUM ('RECEIVED', 'CLASSIFIED', 'REJECTED', 'FAILED');
-- The result sent back to the sender.
CREATE TYPE dmr_result_status AS ENUM ('classified', 'out_of_distribution', 'failed');
-- Sending the result. PENDING: the last try failed with a transient error and the sweeper sends again. SENT, SKIPPED and FAILED are final.
CREATE TYPE dmr_response_status AS ENUM ('PENDING', 'SENT', 'SKIPPED', 'FAILED');
-- rollback DROP TYPE dmr_response_status; DROP TYPE dmr_result_status; DROP TYPE dmr_message_status; DROP TYPE dmr_message_type;

-- changeset Oshan Nanayakkara:global-classifier-dmr-incoming-messages
-- One row per chat message received over DMR: dedupe key, classification and the result sent back to the sender. No message content is stored.
CREATE TABLE public.dmr_incoming_messages (
    -- The incoming envelope id. A redelivery of the same id is not inserted again (ON CONFLICT DO NOTHING) and is answered as a duplicate.
    message_id UUID PRIMARY KEY,
    -- The agency that sent the message (its DMR agent id, assigned by CentOps). The result is sent back to it.
    sender_id UUID NOT NULL,
    -- The envelope's recipientId: the GC's own DMR agent id.
    recipient_id UUID,
    chat_id UUID,
    -- payload.chat.created: when the sender's chat started. Kept verbatim because the result message must repeat it.
    chat_created_at TEXT,
    message_type dmr_message_type,
    sent_at TIMESTAMPTZ,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ,
    sender_known BOOLEAN,
    status dmr_message_status NOT NULL DEFAULT 'RECEIVED',
    error_reason TEXT,
    result_status dmr_result_status,
    top_agency_id UUID,
    top_agency_name TEXT,
    top_confidence NUMERIC,
    classification JSONB,
    response_message_id UUID NOT NULL DEFAULT gen_random_uuid(),
    -- NULL: not sent yet.
    response_status dmr_response_status,
    response_error TEXT,
    response_attempts INTEGER NOT NULL DEFAULT 0,
    response_attempted_at TIMESTAMPTZ,
    responded_at TIMESTAMPTZ
);
CREATE INDEX idx_dmr_incoming_messages_received ON public.dmr_incoming_messages (received_at) WHERE status = 'RECEIVED';
CREATE INDEX idx_dmr_incoming_messages_unanswered ON public.dmr_incoming_messages (processed_at) WHERE status IN ('CLASSIFIED', 'FAILED') AND (response_status IS NULL OR response_status = 'PENDING');
CREATE INDEX idx_dmr_incoming_messages_chat_id ON public.dmr_incoming_messages (chat_id);
-- rollback DROP TABLE public.dmr_incoming_messages;
