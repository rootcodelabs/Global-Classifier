import { DataModel } from 'types/dataModels';

export const validateDataModel = (dataModel: Partial<DataModel>) => {
  const { modelName, datasetId, deploymentEnvironment, baseModels } = dataModel;
  const newErrors: any = {};

  if (!modelName?.trim()) newErrors.modelName = 'Model Name is required';
  if (!deploymentEnvironment?.trim()) newErrors.platform = 'Deployment environent is required';
  if (datasetId === 0) newErrors.dgId = 'Dataset group is required';

  if (baseModels?.length === 0)
    newErrors.baseModels = 'At least one Base Model is required';

  return newErrors;
};

export const customFormattedArray = <T extends Record<string, any>>(
  data: T[] |undefined,
  attributeName: keyof T
) => {
  return data?.map((item) => ({
    label: `${item[attributeName]}`,
    value: item.id,
  }));
};

export const extractedArray = <T extends Record<string, string>>(
  data: T[],
  attributeName: keyof T
): string[] => {
  return data?.map((item) => item[attributeName]);
};

export const dgArrayWithVersions = <T extends Record<string, any>>(
  data: T[],
  attributeName: keyof T
) => {
  return data?.map((item) => ({
    label: `${item[attributeName]} (${item.majorVersion}.${item.minorVersion}.${item.patchVersion})`,
    value: item.dgId,
  }));
};

export const getChangedAttributes = (
  original: Partial<DataModel>,
  updated: Partial<DataModel>
): Partial<Record<keyof DataModel, string | null>> => {
  const changes: Partial<Record<keyof DataModel, string | null>> = {};

  (Object.keys(original) as (keyof DataModel)[]).forEach((key) => {
    if (original[key] !== updated[key]) {
      changes[key] = updated[key] as string | null;
    }else {
      changes[key] = null;
    }
  });

  return changes;
};

