export type TestModelType = {
    majorVersion: number;
    minorVersion: number;
    modelId: number;
    modelName: string;
  };
  
  export type TestModalDropdownSelectionType = {
    label: string;
    value: number;
  };
  
  export type ClassifyTestModalPayloadType = {
    modelId: number | null;
    text: string;
  };
  
  export type ClassifyTestModalResponseType = {
    predictedClasses: string[];
    averageConfidence: number;
    predictedProbabilities: number[];
  };