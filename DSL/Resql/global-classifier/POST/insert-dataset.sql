INSERT INTO public.datasets (
    major,
    minor,
    created_at,
    updated_at,
    generation_status,
    last_model_trained,
    last_trained
) VALUES (
    :major,
    :minor,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    :generationStatus,
    :lastModelTrained,
    CASE WHEN :lastTrained IS NOT NULL THEN :lastTrained::timestamp with time zone ELSE NULL END
)
RETURNING *;