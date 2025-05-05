UPDATE input
SET
    is_corrected = :is_corrected,
    corrected_labels = :corrected_labels::JSONB,
    average_corrected_classes_probability = :average_corrected_classes_probability,
    primary_folder_id = :primary_folder_id
WHERE id = :id;
