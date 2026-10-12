-- liquibase formatted sql

-- changeset Erandi De Silva:global-classifier-sync-status-sync-pending-with-ckb
-- Status for an agency received from CentOps whose data has not been synced yet
ALTER TYPE sync_status ADD VALUE IF NOT EXISTS 'Sync_pending_with_CKB';
-- rollback SELECT 1; -- PostgreSQL cannot drop an enum value
