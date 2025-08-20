UPDATE public.integrated_agencies
SET 
    is_enabled = :isEnabled
WHERE 
    agency_id = :agencyId
RETURNING agency_id;