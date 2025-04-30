import { useQuery } from '@tanstack/react-query';
import { TrainingSessionsStatuses } from 'enums/dataModelsEnums';
import { useEffect, useState } from 'react';
import { getDataModelsProgress } from 'services/data-models';
import sse from 'services/sse-service';
import { TrainingProgressData } from 'types/dataModels';
import { SSEEventData } from 'types/datasetGroups';
import { dataModelsQueryKeys } from 'utils/queryKeys';

export const useTrainingSessions = () => {
  const [progresses, setProgresses] = useState<TrainingProgressData[]>([]);

  const { data: progressData, refetch } = useQuery<TrainingProgressData[]>(
    dataModelsQueryKeys.GET_DATA_MODELS_PROGRESS(),
    getDataModelsProgress,
    {
      onSuccess: (data) => {
        setProgresses(data);
      },
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
            progress.trainingStatus ===
              TrainingSessionsStatuses.TRAINING_SUCCESS_STATUS ||
            progress.trainingStatus ===
              TrainingSessionsStatuses.TRAINING_FAILED_STATUS
          ) && progress.progressPercentage !== 100
      )
      .map((progress) =>
        sse(`/${progress.id}`, 'model', (data: SSEEventData) => {
          handleUpdate(data.sessionId, data);
        })
      );

    return () => {
      eventSources.forEach((eventSource) => eventSource?.close());
    };
  }, [progressData, refetch]);

  return progresses;
};
