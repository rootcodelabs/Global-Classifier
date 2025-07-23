import { useMutation, useQuery } from '@tanstack/react-query';
import { Button, FormSelect, FormTextarea } from 'components';
import CircularSpinner from 'components/molecules/CircularSpinner/CircularSpinner';
import { FC, useState } from 'react';
import { useTranslation } from 'react-i18next';
import apiDev from 'services/api-dev';
import {
  ClassifyTestModalPayloadType,
  TestModalDropdownSelectionType,
  TestModelType,
} from 'types/testModelTypes';

import './TestModel.scss';

const TestModel: FC = () => {
  const { t } = useTranslation();
  const isLoading = false;
  const [modelOptions, setModelOptions] = useState<
    TestModalDropdownSelectionType[]
  >([]);

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

  return (
    <div>
      {isLoading ? (
        <CircularSpinner />
      ) : (
        <div className="container">
          <div className="title_container">
            <div className="title">{t('testModels.title')}</div>
          </div>
          <div style={{ width: '50%' }}>
            <p>{t('testModels.selectionLabel')}</p>
            <div style={{ display: "flex", gap: "1rem" }}>
              <FormSelect
                label=""
                name="modelId"
                options={modelOptions as []}
                placeholder={t('testModels.placeholder') ?? ''}
                onSelectionChange={(selection) => {
                  handleChange('modelId', selection?.value as string);
                }}
              />
              <Button onClick={() => { }}>
                Load Model
              </Button>
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
              onClick={() => { }}
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