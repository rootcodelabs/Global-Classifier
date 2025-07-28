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
    onSuccess: () => {

    },
    onError: () => {

    },
  });

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
                options={toLabelValueArray(modelVersions, 'id', 'version') ?? []}
                placeholder={t('testModels.placeholder') ?? ''}
                onSelectionChange={(selection) => {
                  handleChange('modelId', selection?.value as string);
                }}
                value={testModel?.modelId === null ? t('testModels.errors.modelNotExist') : undefined} defaultValue={testModel?.modelId ?? undefined}
              />
              <Button onClick={() => { setModelLoadingStatus(t('dataModels.loadDataModel.loading') ?? ""), mutation.mutate(testModel.modelId), setColor("#005aa3") }}>
                Load Model
              </Button>
              <div style={{ width: "100%", color: color }} >{modelLoadingStatus}</div>
            </div>
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
              onClick={() => { classifyMutation.mutate(testModel) }}
              disabled={!isClassifyEnabled || !testModel.modelId || !testModel.text}
            >
              {t('testModels.classify')}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default TestModel;