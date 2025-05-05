SELECT json_build_object(
    'dgNames', dgNames,
    'dgVersions', dgVersions,
    'dgValidationStatuses', dgValidationStatuses
)
FROM (
    SELECT
        array_agg(DISTINCT group_name) AS dgNames,
        array_agg(DISTINCT
            major_version::TEXT || '.x.x'
        ) FILTER (WHERE major_version > 0) ||
        array_agg(DISTINCT
            'x.' || minor_version::TEXT || '.x'
        ) FILTER (WHERE minor_version > 0) ||
        array_agg(DISTINCT
            'x.x.' || patch_version::TEXT
        ) FILTER (WHERE patch_version > 0) AS dgVersions,
        array_agg(DISTINCT validation_status) AS dgValidationStatuses
    FROM dataset_group_metadata
) AS subquery;