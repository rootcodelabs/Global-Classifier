-- liquibase formatted sql

-- changeset Erandi De Silva:global-classifier-integrated-agencies-part-of-network
-- Whether the agency is part of the network, as reported by CentOps
ALTER TABLE public.integrated_agencies ADD COLUMN part_of_network BOOLEAN NOT NULL DEFAULT TRUE;
-- rollback ALTER TABLE public.integrated_agencies DROP COLUMN part_of_network;