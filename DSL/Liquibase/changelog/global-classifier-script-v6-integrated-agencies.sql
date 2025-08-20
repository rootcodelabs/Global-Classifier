-- liquibase formatted sql

-- changeset erangi:global-classifier-integrated-agency-enums
-- Create deployment status enum
CREATE TYPE deployment_status AS ENUM ('deployed', 'testing', 'undeployed');

-- Create sync status enum
CREATE TYPE sync_status AS ENUM ('Unavailable_in_CKB', 'Synced_with_CKB','Sync_with_CKB_Failed', 'Resync_needed_with_CKB','Resync_in_progress_with_CKB','Sync_in_progress_with_CKB');

-- changeset erangi:global-classifier-integrated-agency-table
CREATE TABLE public.integrated_agencies (
    agency_id VARCHAR(255) NOT NULL,
    agency_name VARCHAR(255) NOT NULL,
    group_key VARCHAR(255),
    is_latest BOOLEAN NOT NULL DEFAULT TRUE,
    deployment_status deployment_status NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    agency_data_hash VARCHAR(255),
    enable_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    last_model_trained VARCHAR(255),
    last_updated_timestamp TIMESTAMP WITH TIME ZONE,
    last_trained_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    sync_status sync_status,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT integrated_agencies_pkey PRIMARY KEY (agency_id)
);
