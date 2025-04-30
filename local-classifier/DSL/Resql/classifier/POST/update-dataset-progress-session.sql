UPDATE dataset_progress_sessions
SET
    validation_status = :validation_status::Validation_Progress_Status,
    validation_message = :validation_message,
    progress_percentage = :progress_percentage,
    process_complete = :process_complete
WHERE id = :id;