import { FC, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { Button, Card, Dialog } from 'components';
import { useDialog } from 'hooks/useDialog';
import BackArrowButton from 'assets/BackArrowButton';

import DataModelForm from 'components/molecules/DataModelForm';
import { getChangedAttributes } from 'utils/dataModelsUtils';
import { Platform, UpdateType } from 'enums/dataModelsEnums';
import { ButtonAppearanceTypes } from 'enums/commonEnums';
import CircularSpinner from 'components/molecules/CircularSpinner/CircularSpinner';
import { DataModel, UpdatedDataModelPayload } from 'types/dataModels';
import { dataModelsQueryKeys } from 'utils/queryKeys';
import { useTranslation } from 'react-i18next';
import './DataModels.scss';

type ConfigureDataModelType = {
  id: number;
  availableProdModels?: string[];
};

const ConfigureDataModel: FC<ConfigureDataModelType> = ({
  id,
  availableProdModels,
}) => {
  const { t } = useTranslation();
  const { open, close } = useDialog();
  const navigate = useNavigate();
  const [enabled, setEnabled] = useState<boolean>(true);
  const [initialData, setInitialData] = useState<Partial<DataModel>>({
    modelName: '',
    datasetId: 0,
    baseModels: [],
    deploymentEnvironment: '',
    version: '',
  });
  const [dataModel, setDataModel] = useState<DataModel>({
    modelId: 0,
    modelName: '',
    datasetId: 0,
    baseModels: [],
    deploymentEnvironment: '',
    version: '',
  });
  const [modalOpen, setModalOpen] = useState(false);
  const [modalType, setModalType] = useState('');
  const [modalTitle, setModalTitle] = useState<string>('');
  const [modalDiscription, setModalDiscription] = useState<string>('');
  const modalFunciton = useRef(() => { });
 
  const handleDataModelAttributesChange = (
    name: keyof DataModel,
    value: any
  ) => {
    setDataModel((prevDataModel) => ({
      ...prevDataModel,
      [name]: value,
    }));
  };

  const handleSave = () => {
    const payload = getChangedAttributes(initialData, dataModel);
    let updateType: string | undefined;
    if (payload.datasetId) {
      updateType = UpdateType.MAJOR;
    } else if (payload.baseModels) {
      updateType = UpdateType.MINOR;
    } 

    const updatedPayload = {
      modelId: dataModel.modelId,
      connectedDgId: payload.datasetId,
      deploymentEnv: payload.deploymentEnvironment,
      baseModels: payload.baseModels,
      updateType: updateType,
    };

    
  };

  const handleDelete = () => {
    
  };


  const openModal = (
    content: string,
    title: string,
    onConfirm: () => void,
    modalType: string
  ) => {
    setModalOpen(true);
    setModalType(modalType);
    setModalDiscription(content);
    setModalTitle(title);
    modalFunciton.current = onConfirm;
  };
  return (
    <div>
      <div className="container">
        <div className="flex-grid m-30-0">
          <Link to={''} onClick={() => navigate(0)}>
            <BackArrowButton />
          </Link>
          <div className="title">
            {t('dataModels.configureDataModel.title')}
          </div>
        </div>

        <Card>
          <div
            className='metadata-card'
          >
            <div>
              <p>{t('dataModels.configureDataModel.retrainCard')}</p>
              <Button
                onClick={() => {
                }}
              >
                {t('dataModels.configureDataModel.retrain')}
              </Button>
            </div>
          </div>
        </Card>

        {false ? (
          <CircularSpinner />
        ) : (
          <DataModelForm
            dataModel={dataModel}
            handleChange={handleDataModelAttributesChange}
            type="configure"
          />
        )}
      </div>
      <div
        className="flex data-model-buttons"
      >
        <Button
          appearance="error"
          // disabled={deleteDataModelMutation.isLoading}
          // showLoadingIcon={deleteDataModelMutation.isLoading}
          onClick={() => handleDelete()}
        >
          {t('dataModels.configureDataModel.deleteModal')}
        </Button>
        <Button
          disabled={!dataModel.datasetId || dataModel.datasetId === 0}
          onClick={() => {}
          }
        >
          {t('dataModels.configureDataModel.retrain')}
        </Button>
        <Button
          // disabled={updateDataModelMutation.isLoading}
          // showLoadingIcon={updateDataModelMutation.isLoading}
          onClick={handleSave}
        >
          {t('dataModels.configureDataModel.save')}
        </Button>
      </div>

      <Dialog
        onClose={() => setModalOpen(false)}
        isOpen={modalOpen}
        title={modalTitle}
        footer={
          <div className="flex-grid">
            <Button
              appearance={ButtonAppearanceTypes.SECONDARY}
              onClick={() => setModalOpen(false)}
            >
              {t('global.cancel')}
            </Button>
            {modalType === 'retrain' ? (
              <Button
                // disabled={retrainDataModelMutation.isLoading || !dataModel.datasetId || dataModel.datasetId === 0}
                // showLoadingIcon={retrainDataModelMutation.isLoading}
                onClick={() => modalFunciton.current()}
              >
                {t('dataModels.configureDataModel.retrain')}
              </Button>
            ) : modalType === 'delete' ? (
              <Button
                // disabled={deleteDataModelMutation.isLoading}
                // showLoadingIcon={deleteDataModelMutation.isLoading}
                onClick={() => modalFunciton.current()}
                appearance={ButtonAppearanceTypes.ERROR}
              >
                {t('global.delete')}
              </Button>
            ) : (
              <Button
                // disabled={updateDataModelMutation.isLoading}
                // showLoadingIcon={updateDataModelMutation.isLoading}
                onClick={() => modalFunciton.current()}
              >
                {t('global.proceed')}
              </Button>
            )}
          </div>
        }
      >
        <div className="form-container">{modalDiscription}</div>
      </Dialog>
    </div>
  );
};

export default ConfigureDataModel;