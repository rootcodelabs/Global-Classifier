INSERT INTO public.dataset_metadata (
    dataset_id,
    chunk_id,
    included_agencies,
    created_at
) VALUES (
    :datasetId,
    :chunkId,
    :includedAgencies::jsonb,
    NOW()
)