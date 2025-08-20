UPDATE public.integrated_agencies
    SET 
        sync_status =  :syncStatus::sync_status,
        agency_data_hash = :agencyDataHash,
        last_updated_timestamp = CURRENT_TIMESTAMP
    WHERE 
        agency_id = :agencyId;