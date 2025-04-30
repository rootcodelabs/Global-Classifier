INSERT INTO "dataset_group_metadata" (
    group_name,
    group_key,
    major_version,
    minor_version,
    patch_version,
    latest,
    is_enabled,
    enable_allowed,
    created_timestamp,
    last_updated_timestamp,
    validation_status,
    processed_data_available,
    raw_data_available,
    num_samples,
    num_pages,
    validation_criteria,
    class_hierarchy
     )
     VALUES (
    :group_name,
    :group_key,
    :major_version,
    :minor_version,
    :patch_version,
    :latest,
    :is_enabled,
    :enable_allowed,
    :created_timestamp::timestamp with time zone,
    :last_updated_timestamp::timestamp with time zone,
    :validation_status::Validation_Status,
    :processed_data_available,
    :raw_data_available,
    :num_samples,
    :num_pages,
    :validation_criteria::jsonb,
    :class_hierarchy::jsonb
)RETURNING id;

