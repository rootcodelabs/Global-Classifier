import { FC, useEffect, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Button, Card, Dialog } from 'components';
import { useDialog } from 'hooks/useDialog';
import BackArrowButton from 'assets/BackArrowButton';

import DataModelForm from 'components/molecules/DataModelForm';
import { getChangedAttributes } from 'utils/dataModelsUtils';
import { Maturity, UpdateType } from 'enums/dataModelsEnums';
import { ButtonAppearanceTypes } from 'enums/commonEnums';
import CircularSpinner from 'components/molecules/CircularSpinner/CircularSpinner';
import { DataModel, UpdatedDataModelPayload } from 'types/dataModels';
import { dataModelsQueryKeys } from 'utils/queryKeys';
import { useTranslation } from 'react-i18next';
import './DataModels.scss';
import { configureDataModel, deleteDataModel, getDataModelMetadata, getProductionDataModel } from 'services/datamodels';
import { use } from 'i18next';
import { set } from 'date-fns';
import { areArraysEqual } from 'utils/commonUtilts';

const ConfigureDataModel: FC = () => {
  const { t } = useTranslation();
  const { open, close } = useDialog();
  const navigate = useNavigate();
  const [modalOpen, setModalOpen] = useState(false);
  const [modalType, setModalType] = useState('');
  const [modalTitle, setModalTitle] = useState<string>('');
  const [modalDiscription, setModalDiscription] = useState<string>('');
  const modalFunciton = useRef(() => { });
  const [searchParams] = useSearchParams();
  const modelId = searchParams.get('datamodelId');

  const { data: modelMetadata } = useQuery({
    queryKey: dataModelsQueryKeys.GET_META_DATA(modelId ?? ''),
    queryFn: () => getDataModelMetadata(modelId ?? ''),
  });

  const { data: prodDataModel, isLoading: isProdDataModelLoading } = useQuery({
    queryKey: dataModelsQueryKeys.GET_PROD_DATA_MODEL(),
    queryFn: () => getProductionDataModel(),
  });

  const [initialData, setInitialData] = useState<Partial<DataModel>>({
    modelName: modelMetadata?.modelName,
    datasetId: modelMetadata?.connectedDsId,
    baseModels: modelMetadata?.baseModels,
    deploymentEnvironment: modelMetadata?.deploymentEnv,
    version: `V${modelMetadata?.major}.${modelMetadata?.minor}`,
  });

  const [dataModel, setDataModel] = useState<DataModel>({
    modelId: modelMetadata?.modelId,
    modelName: modelMetadata?.modelName,
    datasetId: modelMetadata?.connectedDsId.toString(),
    baseModels: modelMetadata ? JSON.parse(modelMetadata?.baseModels.value) : [],
    deploymentEnvironment: modelMetadata?.deploymentEnv,
    version: `V${modelMetadata?.major}.${modelMetadata?.minor}`,
    trainingResults: modelMetadata?.trainingResults,
  });

  useEffect(() => {
    setInitialData({
      modelId: modelMetadata?.modelId,
      modelName: modelMetadata?.modelName,
      datasetId: modelMetadata?.connectedDsId.toString(),
      baseModels: modelMetadata ? JSON.parse(modelMetadata?.baseModels.value) : [],
      deploymentEnvironment: modelMetadata?.deploymentEnv,
      version: `V${modelMetadata?.major}.${modelMetadata?.minor}`,
    });
    setDataModel({
      modelId: modelMetadata?.modelId,
      modelName: modelMetadata?.modelName,
      datasetId: modelMetadata?.connectedDsId.toString(),
      baseModels: modelMetadata ? JSON.parse(modelMetadata?.baseModels.value) : [],
      deploymentEnvironment: modelMetadata?.deploymentEnv,
      version: `V${modelMetadata?.major}.${modelMetadata?.minor}`,
      trainingResults: modelMetadata?.trainingResults,

    });
  }, [modelMetadata]);


  const handleDataModelAttributesChange = (
    name: keyof DataModel,
    value: any
  ) => {
    setDataModel((prevDataModel) => ({
      ...prevDataModel,
      [name]: value,
    }));
  };

  const updateMutation = useMutation({
    mutationFn: configureDataModel,
    onSuccess: () => {
      open({
        title: t('dataModels.configureDataModel.saveChangesTitile'),
        content: t('dataModels.configureDataModel.saveChangesDesc'),
        footer: (<div className='flex-grid'><Button appearance={ButtonAppearanceTypes.SECONDARY} onClick={() => { close() }}>Close</Button><Button onClick={() => { navigate('/data-models'), close() }}>View all Data Models</Button></div>)
      });

    },
    onError: () => {
      open({
        title: t('dataModels.configureDataModel.updateErrorTitile'),
        content: t('dataModels.configureDataModel.updateErrorDesc'),
      });
    },
  });

  const handleSaveChanges = () => {
    const payload = getChangedAttributes(initialData, dataModel);
    let updateType: string | undefined;
    if (payload.datasetId) {
      updateType = UpdateType.MAJOR;
    } else if (payload.baseModels) {
      updateType = UpdateType.MINOR;
    }

    const updatedPayload = {
      modelGroupKey: modelMetadata.modelGroupKey ?? "",
      modelName: dataModel.modelName ?? "",
      connectedDsId: Number(dataModel.datasetId) ?? 0,
      deploymentEnv: dataModel.deploymentEnvironment ?? "",
      baseModels: dataModel.baseModels ?? [],
      connectedDsMajorVersion: Number(dataModel.version?.split('.')[0]?.[1]) ?? 0,
      connectedDsMinorVersion: Number(dataModel.version?.split('.')[1]) ?? 0,
      updateType: updateType ?? "",
    };

    if (updateType) {
      if (prodDataModel && dataModel.deploymentEnvironment === "production") {
        openModal(
          t('dataModels.createDataModel.replaceDesc'),
          t('dataModels.createDataModel.replaceTitle'),
          () => updateMutation.mutate(updatedPayload),
          'replace'
        );
      } else {
        updateMutation.mutate(updatedPayload);
      }
    }

  };

  const deleteDataModelMutation = useMutation({
    mutationFn: deleteDataModel,
    onSuccess: () => {
      open({
        title: t('dataModels.configureDataModel.deleteModalSuccessTitle'),
        content: t('dataModels.configureDataModel.deleteModalSuccessDesc'),
        footer: (
          <div className='flex-grid'>
            <Button onClick={() => { navigate('/data-models'); close(); }}>View all Data Models</Button>
          </div>
        ),
      });
    },
    onError: () => {
      open({
        title: t('dataModels.configureDataModel.deleteModalErrorTitle'),
        content: t('dataModels.configureDataModel.deleteModalErrorDesc'),
      });
    },
  });

  const handleDelete = () => {
    if (dataModel.deploymentEnvironment === Maturity.PRODUCTION) {
      openModal(
        t('dataModels.configureDataModel.deleteErrorDesc'),
        t('dataModels.configureDataModel.deleteErrorTitle'),
        () => navigate('/data-models'),
        'warning'
      );
    } else {
      openModal(
        t('dataModels.configureDataModel.deleteConfirmationDesc'),
        t('dataModels.configureDataModel.deleteConfirmation'),
        () => deleteDataModelMutation.mutate(modelId),
        'delete'
      );
    }

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
          <Link to={'/data-models'}>
            <BackArrowButton />
          </Link>
          <div className="title">
            {t('dataModels.configureDataModel.title')}
          </div>
        </div>

        {modelMetadata?.modelStatus === "deprecated" && (
          <div
            className='metadata-card'
          >
            <div>
              <p>{t('dataModels.configureDataModel.retrainCard')}</p>
              <Button
                onClick={() => {
                }}
                appearance={ButtonAppearanceTypes.ERROR}
              >
                {t('dataModels.configureDataModel.retrain')}
              </Button>
            </div>
          </div>
        )}
        {false ? (
          <CircularSpinner />
        ) : (
          <DataModelForm
            dataModel={
              dataModel
            }
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
          disabled={deleteDataModelMutation.isLoading}
          showLoadingIcon={deleteDataModelMutation.isLoading}
          onClick={() => handleDelete()}
        >
          {t('dataModels.configureDataModel.deleteModal')}
        </Button>
       
        <Button
          disabled={updateMutation.isLoading || (initialData.datasetId === dataModel.datasetId && initialData.deploymentEnvironment === dataModel.deploymentEnvironment && areArraysEqual(initialData.baseModels as string[], dataModel.baseModels as string[]))}
          showLoadingIcon={updateMutation.isLoading}
          onClick={handleSaveChanges}
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
                disabled={deleteDataModelMutation.isLoading}
                showLoadingIcon={deleteDataModelMutation.isLoading}
                onClick={() => modalFunciton.current()}
                appearance={ButtonAppearanceTypes.ERROR}
              >
                {t('global.delete')}
              </Button>
            ) : modalType === 'replace' ? (
              <Button
                disabled={updateMutation.isLoading}
                showLoadingIcon={updateMutation.isLoading}
                onClick={() => modalFunciton.current()}
                appearance={ButtonAppearanceTypes.PRIMARY}
              >
                {t('global.replace')}
              </Button>
            )
              : modalType === 'warning' ? (
                <Button
                  onClick={() => modalFunciton.current()}
                  appearance={ButtonAppearanceTypes.PRIMARY}
                >
                  View all Data Models
                </Button>
              )
                : (
                  null
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