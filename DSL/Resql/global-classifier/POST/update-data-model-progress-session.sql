UPDATE model_progress_sessions
SET
    training_progress_status = :training_progress_status::Training_Progress_Status,
    training_message = :training_message,
    progress_percentage = :progress_percentage,
    process_complete = :process_complete
WHERE id = :id;