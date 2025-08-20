SELECT chunk_id
FROM public.dataset_metadata
WHERE EXISTS (
  SELECT 1
  FROM jsonb_array_elements_text(included_agencies) AS elem
  WHERE elem = :agencyId::text
);