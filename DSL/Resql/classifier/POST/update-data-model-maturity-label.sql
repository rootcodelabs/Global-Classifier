UPDATE models_metadata
SET
    maturity_label = :maturity_label::Maturity_Label
WHERE id = :id;
