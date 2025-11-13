-- Insert agency presigned URL
INSERT INTO public.mock_ckb (agency_id, agency_data_hash, data_url)
VALUES (:agencyId, :agencyDataHash, :dataUrl);