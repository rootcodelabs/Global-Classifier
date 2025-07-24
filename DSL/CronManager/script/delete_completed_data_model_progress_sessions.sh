#!/bin/bash

cd "$(dirname "$0")"

source ../config/config.ini

script_name=$(basename $0)
pwd

echo $(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - $script_name started

delete_dataset_progress_sessions() {
  delete_response=$(curl -s -X POST -H "Content-Type: application/json" "http://resql:8082/delete-completed-data-model-progress-sessions")

  echo "Response from delete request: $delete_response"

  session_ids=$(echo "$delete_response" | grep -oP '"id":\K\d+' | tr '\n' ' ' | sed 's/ $//')  # Remove trailing space

  echo "Session IDs: $session_ids"

  if [ -n "$session_ids" ]; then
    delete_from_opensearch "$session_ids"
  else
    echo "No session IDs were returned in the response."
  fi
}

delete_from_opensearch() {
  local session_ids="$1"

  delete_query="{\"query\": {\"terms\": {\"sessionId\": ["
  for id in $session_ids; do
    delete_query+="\"$id\","
  done
  delete_query=$(echo "$delete_query" | sed 's/,$//') # Remove trailing comma
  delete_query+="]}}}"

  echo "delete query: $delete_query"

  opensearch_response=$(curl -s -X POST -H "Content-Type: application/json" -d "$delete_query" "http://opensearch-node:9200/data_model_progress_sessions/_delete_by_query")

  echo "Response from OpenSearch delete request: $opensearch_response"
}

delete_dataset_progress_sessions

echo $(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - $script_name finished
