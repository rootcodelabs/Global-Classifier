import { useQuery } from '@tanstack/react-query';
import { ValidationSessionsStatuses } from 'enums/datasetEnums';
import { useEffect, useState } from 'react';
import { getDatasetGroupsProgress } from 'services/datasets';
import sse from 'services/sse-service';
import { SSEEventData, ValidationProgressData } from 'types/datasetGroups';
import { datasetQueryKeys } from 'utils/queryKeys';

export const useValidationSessions = () => {
  const [progresses, setProgresses] = useState<ValidationProgressData[]>([]);

  const { data: progressData, refetch } = useQuery<ValidationProgressData[]>(
    datasetQueryKeys.GET_DATASET_GROUP_PROGRESS(),
    getDatasetGroupsProgress,
    {
      onSuccess: (data) => setProgresses(data),
    }
  );

  const handleUpdate = (sessionId: string, newData: SSEEventData) => {
    setProgresses((prevProgresses) =>
      prevProgresses.map((progress) =>
        progress.id === sessionId ? { ...progress, ...newData } : progress
      )
    );
  };

  useEffect(() => {
    if (!progressData) return;

    const eventSources = progressData
      .filter(
        (progress) =>
          !(
            progress.validationStatus ===
              ValidationSessionsStatuses.VALIDATION_SUCCESS_STATUS ||
            progress.validationStatus ===
              ValidationSessionsStatuses.VALIDATION_FAILED_STATUS
          ) && progress.progressPercentage !== 100
      )
      .map((progress) =>
        sse(`/${progress.id}`, 'dataset', (data: SSEEventData) => {
          handleUpdate(data.sessionId, data);
        })
      );

    return () => {
      eventSources.forEach((eventSource) => eventSource?.close());
    };
  }, [progressData, refetch]);

  return progresses;
};
