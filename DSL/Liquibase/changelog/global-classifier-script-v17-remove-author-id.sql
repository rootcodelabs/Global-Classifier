-- liquibase formatted sql

-- changeset thiru.dinesh:v17-remove-author-id
-- comment: Remove author_id column from inference_logs table for privacy compliance

ALTER TABLE public.inference_logs DROP COLUMN IF EXISTS author_id;

-- rollback: ALTER TABLE public.inference_logs ADD COLUMN author_id character varying(255) NOT NULL;
