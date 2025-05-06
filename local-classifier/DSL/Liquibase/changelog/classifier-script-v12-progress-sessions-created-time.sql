-- liquibase formatted sql

-- changeset kalsara Magamage:classifier-script-v12-changeset1
ALTER TABLE dataset_progress_sessions
ADD COLUMN created_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

-- changeset kalsara Magamage:classifier-script-v12-changeset2
ALTER TABLE model_progress_sessions
ADD COLUMN created_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

