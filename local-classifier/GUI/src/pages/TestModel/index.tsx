import { useMutation, useQuery } from '@tanstack/react-query';
import { Button, FormSelect, FormTextarea } from 'components';
import CircularSpinner from 'components/molecules/CircularSpinner/CircularSpinner';
import { FC, useState } from 'react';
import { useTranslation } from 'react-i18next';
import apiDev from 'services/api-dev';
import {
  ClassifyTestModalPayloadType,
  ClassifyTestModalResponseType,
  TestModalDropdownSelectionType,
  TestModelType,
} from 'types/testModelTypes';
import { formatClassHierarchyArray } from 'utils/commonUtilts';
import { testModelsEndpoints } from 'utils/endpoints';
import { testModelsQueryKeys } from 'utils/queryKeys';
import { formatPredictions } from 'utils/testModelUtil';
import './TestModel.scss';

const TestModel: FC = () => {
  const { t } = useTranslation();

  const [modelOptions, setModelOptions] = useState<
    TestModalDropdownSelectionType[]
  >([]);

  const [testModel, setTestModel] = useState<ClassifyTestModalPayloadType>({
    modelId: null,
    text: '',
  });
  const { isLoading } = useQuery({
    queryKey: testModelsQueryKeys.GET_TEST_MODELS(),
    queryFn: async () => {
      const response = await apiDev.get(testModelsEndpoints.GET_MODELS());
      return response?.data?.response?.data ?? ([] as TestModelType[]);
    },
    onSuccess: (data: TestModelType[]) => {
      if (data && data.length > 0) {
        setModelOptions(
          data?.map((options) => ({
            label: options.modelName,
            value: options.modelId,
          }))
        );
      }
    },
  });

  const {
    data: classifyData,
    isLoading: classifyLoading,
    mutate,
  } = useMutation({
    mutationFn: async (data: ClassifyTestModalPayloadType) => {
      const response = await apiDev.post(
        testModelsEndpoints.CLASSIFY_TEST_MODELS(),
        data
      );
      return response?.data?.response?.data as ClassifyTestModalResponseType;
    },
  });

  const handleChange = (key: string, value: string | number) => {
    setTestModel((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  return (
    <div>
      {isLoading ? (
        <CircularSpinner />
      ) : (
        <div className="container">
          <div className="title_container">
            <div className="title">{t('testModels.title')}</div>
          </div>
          <div className="grey-card">
            <FormSelect
              label={t('testModels.selectionLabel')}
              name="modelId"
              options={modelOptions as []}
              placeholder={t('testModels.placeholder') ?? ''}
              onSelectionChange={(selection) => {
                handleChange('modelId', selection?.value as string);
              }}
            />
          </div>

          <div className="testModalFormTextArea">
            <p>{t('testModels.classifyTextLabel')}</p>
            <FormTextarea
              label=""
              name=""
              maxLength={1000}
              onChange={(e) => handleChange('text', e.target.value)}
              showMaxLength={true}
            />
          </div>
          <div className="testModalClassifyButton">
            <Button
              disabled={testModel.text === ''  || classifyLoading}
              onClick={() => mutate(testModel)}
              showLoadingIcon={classifyLoading}
            >
              {t('testModels.classify')}
            </Button>
          </div>

          {!classifyLoading && classifyData && (
            <div className='mt-20'>
              <div className="blue-card">
                <div className="flex">
                  <b>{t('testModels.predictedHierarchy')}</b>
                  <p>
                    {classifyData?.predictedClasses &&
                      formatClassHierarchyArray(classifyData?.predictedClasses)}
                  </p>
                </div>
              </div>
              <div className="blue-card">
                <div className="flex">
                  <b>{t('testModels.averageConfidence')}</b>
                  <p>{classifyData?.averageConfidence ?? ''}</p>
                </div>
              </div>
              <div className="blue-card">
                <div>
                  <b>{t('testModels.classProbabilities')}</b>
                  <ul className="testModalList">
                    {formatPredictions(classifyData)?.map((prediction, index) => {
                      return <li key={`pred${index}`}>{prediction}</li>;
                    })}
                  </ul>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default TestModel;