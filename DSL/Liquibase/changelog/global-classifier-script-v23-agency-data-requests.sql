-- liquibase formatted sql

-- changeset Erandi De Silva:global-classifier-agency-request-status-enum
-- Create agency data request status enum
CREATE TYPE agency_request_status AS ENUM ('PENDING', 'IN_PROGRESS', 'DONE', 'FAILED', 'EXPIRED', 'CANCELLED');
-- rollback DROP TYPE agency_request_status;

-- changeset Erandi De Silva:global-classifier-agency-data-requests-table
-- Agency data received from CentOps, waiting for or going through dataset generation
CREATE TABLE public.agency_data_requests (
    id                 BIGSERIAL PRIMARY KEY,
    agency_id          VARCHAR(255) NOT NULL,
    data_hash          VARCHAR(255) NOT NULL,
    presigned_url      TEXT NOT NULL,
    url_expires_at     TIMESTAMP WITH TIME ZONE NOT NULL,
    status             agency_request_status NOT NULL DEFAULT 'PENDING',
    dataset_version_id BIGINT,
    retry_count        INT NOT NULL DEFAULT 0,
    error_message      TEXT,
    received_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
-- rollback DROP TABLE public.agency_data_requests;

-- changeset Erandi De Silva:global-classifier-agency-data-requests-indexes
-- At most one PENDING request per agency
CREATE UNIQUE INDEX one_pending_per_agency ON public.agency_data_requests (agency_id) WHERE status = 'PENDING';
CREATE INDEX idx_agency_data_requests_status ON public.agency_data_requests (status);
CREATE INDEX idx_agency_data_requests_dataset ON public.agency_data_requests (dataset_version_id);
-- rollback DROP INDEX IF EXISTS public.idx_agency_data_requests_dataset; DROP INDEX IF EXISTS public.idx_agency_data_requests_status; DROP INDEX IF EXISTS public.one_pending_per_agency;