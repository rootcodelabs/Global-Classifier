SELECT predicted_labels, corrected_labels
FROM "input"
WHERE input_id=:inputId AND platform='JIRA';
