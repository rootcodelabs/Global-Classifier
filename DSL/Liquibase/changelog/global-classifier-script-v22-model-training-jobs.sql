-- liquibase formatted sql

-- changeset thiru.dinesh:global-classifier-model-training-jobs-add-failed-status
-- Add 'training-failed' status to existing training_job_status enum
ALTER TYPE training_job_status ADD VALUE 'training-failed';