INSERT INTO stop_words (stop_word)
SELECT unnest(ARRAY[:stop_words])
ON CONFLICT (stop_word) DO NOTHING;