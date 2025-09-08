import { useMutation, useQuery } from '@tanstack/react-query';
import { Button, FormSelect, FormTextarea } from 'components';
import CircularSpinner from 'components/molecules/CircularSpinner/CircularSpinner';
import { FC, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ClassifyTestModalPayloadType
} from 'types/testModelTypes';

import './TestModel.scss';
import { dataModelsQueryKeys } from 'utils/queryKeys';
import { classify, getAllModelVersions, loadModel } from 'services/datamodels';
import { toLabelValueArray } from 'utils/commonUtilts';
import { useDialog } from 'hooks/useDialog';

const TestModel: FC = () => {
  const { t } = useTranslation();
  const isLoading = false;
  const [modelLoadingStatus, setModelLoadingStatus] = useState<string>("");
  const [color, setColor] = useState<string>("black");
  const [isClassifyEnabled, setIsClassifyEnabled] = useState<boolean>(false);
  const [classificationResult, setClassificationResult] = useState<any>([]);

  const { open } = useDialog();

  const { data: modelVersions } = useQuery({
    queryKey: dataModelsQueryKeys.GET_ALL_DATA_MODELS_VERSIONS(),
    queryFn: () => getAllModelVersions(),
  });

  const [testModel, setTestModel] = useState<ClassifyTestModalPayloadType>({
    modelId: null,
    text: '',
  });

  const handleChange = (key: string, value: string | number) => {
    setTestModel((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const mutation = useMutation({
    mutationFn: loadModel,
    onSuccess: () => {
      setModelLoadingStatus(t('dataModels.loadDataModel.loaded') ?? "");
      setColor("#2c7a4c");
      setIsClassifyEnabled(true);
    },
    onError: () => {
      open({
        title: t('dataModels.loadDataModel.errorTitle'),
        content: t('dataModels.loadDataModel.errorDesc'),
      });
      setModelLoadingStatus(t('dataModels.loadDataModel.errorTitle') ?? "");
      setColor("#d73e3e");
    },
  });

  const classifyMutation = useMutation({
    mutationFn: classify,
    onSuccess: (data) => {
      setClassificationResult(data);
    },
    onError: () => {
      open({
        title: t('testModels.error'),
        content: t('testModels.errorDesc'),
      });
    },
  });

  const processClassificationResult = (result: any) => {
    if (!result || !Array.isArray(result) || result.length === 0) return [];

    // Get the first array (which contains the classification results)
    const resultData = result[0];

    // Check if resultData is an array of classification objects
    if (!Array.isArray(resultData)) return [];

    return resultData.map((item: any, index: number) => {
      return {
        rank: index + 1,
        agencyId: item.agency_id,
        agencyName: item.agency_name?.replace(/_/g, ' ') || `Agency ${item.agency_id}`,
        confidence: item.confidence || 0
      };
    }).sort((a, b) => b.confidence - a.confidence); // Sort by confidence descending
  };

  const processedResults = classificationResult ? processClassificationResult(classificationResult) : [];


  return (
    <div>
      {isLoading ? (
        <CircularSpinner />
      ) : (
        <div className="container">
          <div className="title_container">
            <div className="title">{t('testModels.title')}</div>
          </div>
          <div style={{ width: '70%' }}>
            <p>{t('testModels.selectionLabel')}</p>
            <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>

              <FormSelect
                label=""
                name="modelId"
                options={modelVersions ? toLabelValueArray(modelVersions, 'id', 'version') ?? [] : []}
                placeholder={t('testModels.placeholder') ?? ''}
                onSelectionChange={(selection) => {
                  handleChange('modelId', selection?.value as string);
                  setIsClassifyEnabled(false);
                }}
                value={testModel?.modelId === null ? t('testModels.errors.modelNotExist') : undefined} defaultValue={testModel?.modelId ?? undefined}
              />
              <Button showLoadingIcon={mutation.isLoading} disabled={!testModel.modelId || mutation.isLoading} onClick={() => { setModelLoadingStatus(t('dataModels.loadDataModel.loading') ?? ""); mutation.mutate(testModel.modelId); setColor("#005aa3"); }}>
                Load Model
              </Button>
              <div style={{ width: "100%", color: color }} >{modelLoadingStatus}</div>
            </div>
          </div>

          <div className="testModalFormTextArea">
            <p>{t('testModels.classifyTextLabel')}</p>
            <FormTextarea
              label=""
              name="text"
              maxLength={1000}
              onChange={(e) => handleChange('text', e.target.value)}
              showMaxLength={true}
            />
          </div>
          <div className="testModalClassifyButton">
            <Button
              onClick={() => { classifyMutation.mutate(testModel) }}
              disabled={!isClassifyEnabled || !testModel.modelId || !testModel.text || !testModel.text.trim() || classifyMutation.isLoading}
              showLoadingIcon={classifyMutation.isLoading}
            >
              {t('testModels.classify')}
            </Button>
          </div>

          {processedResults.length > 0 && (
            <div className="classification-results">
              <h3>{t('testModels.results') || 'Classification Results'}</h3>
              <div className="results-container">
                <div className="top-prediction">
                  <h4>{t('testModels.topPrediction') || 'Top Prediction'}</h4>
                  <div className="prediction-card primary">
                    <div className="agency-name">
                      {processedResults[0].agencyName}
                    </div>
                    <div className="confidence-score">
                      {(processedResults[0].confidence).toFixed(10)}
                    </div>
                  </div>
                </div>
                {processedResults.length > 1 && (
                  <div className="all-predictions">
                    <h4>{t('testModels.allPredictions') || 'All Predictions'}</h4>
                    <div className="predictions-list">
                      {processedResults.map((result, index) => (
                        <div
                          key={`${result.rank}-${result.agencyName}`}
                          className={`prediction-item ${index === 0 ? 'highest' : ''}`}
                        >
                          <div className="rank">#{index + 1}</div>
                          <div className="agency-info">
                            <span className="agency-name">
                              {result.agencyName}
                            </span>
                            <div className="confidence-bar-container">
                              <div
                                className="confidence-bar"
                                style={{ width: `${result.confidence * 100}%` }}
                              />
                            </div>
                          </div>
                          <div className="confidence-percentage">
                            {(result.confidence).toFixed(10)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Error State */}
          {classifyMutation.isError && (
            <div className="classification-error">
              <p>{t('testModels.classificationFailed') || 'Classification failed. Please try again.'}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default TestModel;