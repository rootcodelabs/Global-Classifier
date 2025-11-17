-- Check if agency exists in mock_centops table
SELECT agency_id
FROM public.mock_centops
WHERE agency_id = :agencyId;
