export type InferencePayload = {
  averageCorrectedClassesProbability: number | null;
  averagePredictedClassesProbability: number;
  correctedLabels: string[] | null;
  inferenceId: number;
  inferenceText: string;
  inferenceTimeStamp: string;
  inputId: string;
  platform: string;
  predictedLabels: string[];
  totalPages: number;
};