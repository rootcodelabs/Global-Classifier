-- liquibase formatted sql

-- changeset Oshan Nanayakkara:global-classifier-dmr-incoming-messages
-- One row per chat message received over DMR: dedupe key, classification and the result sent back to the sender. No message content is stored.
CREATE TABLE public.dmr_incoming_messages (
    id BIGSERIAL PRIMARY KEY,
    message_id UUID NOT NULL UNIQUE,
    sender_id VARCHAR(255) NOT NULL,
    recipient_id VARCHAR(255),
    chat_id VARCHAR(255),
    chat_created TEXT,
    message_type VARCHAR(50),
    sent_at TIMESTAMPTZ,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ,
    sender_known BOOLEAN,
    status VARCHAR(20) NOT NULL DEFAULT 'RECEIVED'
        CHECK (status IN ('RECEIVED', 'CLASSIFIED', 'REJECTED', 'FAILED')),
    error_reason TEXT,
    result_status VARCHAR(30)
        CHECK (result_status IN ('classified', 'out_of_distribution', 'failed')),
    top_agency_id VARCHAR(255),
    top_agency_name VARCHAR(255),
    top_confidence NUMERIC,
    classification JSONB,
    response_message_id UUID NOT NULL DEFAULT gen_random_uuid(),
    -- NULL: not sent yet. PENDING: the last try failed with a transient error and the sweeper sends again. SENT, SKIPPED and FAILED are final.
    response_status VARCHAR(20)
        CHECK (response_status IN ('PENDING', 'SENT', 'SKIPPED', 'FAILED')),
    response_error TEXT,
    response_attempts INTEGER NOT NULL DEFAULT 0,
    response_attempted_at TIMESTAMPTZ,
    responded_at TIMESTAMPTZ
);
CREATE INDEX idx_dmr_incoming_messages_received ON public.dmr_incoming_messages (received_at) WHERE status = 'RECEIVED';
CREATE INDEX idx_dmr_incoming_messages_unanswered ON public.dmr_incoming_messages (processed_at) WHERE status IN ('CLASSIFIED', 'FAILED') AND (response_status IS NULL OR response_status = 'PENDING');
CREATE INDEX idx_dmr_incoming_messages_chat_id ON public.dmr_incoming_messages (chat_id);
-- rollback DROP TABLE public.dmr_incoming_messages;
