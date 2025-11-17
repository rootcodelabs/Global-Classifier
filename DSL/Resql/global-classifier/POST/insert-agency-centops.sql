-- Insert new agency into mock_centops table
INSERT INTO public.mock_centops (agency_id, agency_name, created_at)
VALUES (:agencyId, :agencyName, NOW());
