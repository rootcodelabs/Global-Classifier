import { PredictionInput } from "types/testModel";

export function formatPredictions(input: PredictionInput): string[] {
    const { predictedClasses, predictedProbabilities } = input;
    
    return predictedClasses.map((predictedClass, index) => {
      const probability = predictedProbabilities[index];
      return `${predictedClass} - ${probability}%`;
    });
  }