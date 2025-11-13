-- Update agency presigned URL
UPDATE public.mock_ckb
SET 
    data_url = :dataUrl,
    created_at = NOW()
WHERE agency_id = :agencyId;