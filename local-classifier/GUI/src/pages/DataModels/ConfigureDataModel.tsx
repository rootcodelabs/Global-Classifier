import { FC, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { Button, Card, Dialog } from 'components';
import { useDialog } from 'hooks/useDialog';
import BackArrowButton from 'assets/BackArrowButton';
import {
  deleteDataModel,
  getMetadata,
  retrainDataModel,
  updateDataModel,
} from 'services/data-models';
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
    dgId: 0,
    platform: '',
    baseModels: [],
    maturity: '',
    version: '',
  });
  const [dataModel, setDataModel] = useState<DataModel>({
    modelId: 0,
    modelName: '',
    dgId: 0,
    platform: '',
    baseModels: [],
    maturity: '',
    version: '',
  });
  const [modalOpen, setModalOpen] = useState(false);
  const [modalType, setModalType] = useState('');
  const [modalTitle, setModalTitle] = useState<string>('');
  const [modalDiscription, setModalDiscription] = useState<string>('');
  const modalFunciton = useRef(() => { });
  const { isLoading } = useQuery(
    dataModelsQueryKeys.GET_META_DATA(id),
    () => getMetadata(id),
    {
      enabled,
      onSuccess: (data) => {
        setDataModel({
          modelId: data?.modelId || 0,
          modelName: data?.modelName || '',
          dgId: data?.connectedDgId || 0,
          platform: data?.deploymentEnv || '',
          baseModels: data?.baseModels || [],
          maturity: data?.maturityLabel || '',
          version: `V${data?.majorVersion}.${data?.minorVersion}`,
        });
        setInitialData({
          modelName: data?.modelName || '',
          dgId: data?.connectedDgId || 0,
          platform: data?.deploymentEnv || '',
          baseModels: data?.baseModels || [],
          maturity: data?.maturityLabel || '',
          version: `V${data?.majorVersion}.${data?.minorVersion}`,
        });
        setEnabled(false);
      },
    }
  );

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
    if (payload.dgId) {
      updateType = UpdateType.MAJOR;
    } else if (payload.baseModels || payload.platform) {
      updateType = UpdateType.MINOR;
    } else if (payload.maturity) {
      updateType = UpdateType.MATURITY_LABEL;
    }

    const updatedPayload = {
      modelId: dataModel.modelId,
      connectedDgId: payload.dgId,
      deploymentEnv: payload.platform,
      baseModels: payload.baseModels,
      maturityLabel: payload.maturity,
      updateType: updateType,
    };

    if (updateType) {
      if (availableProdModels?.includes(dataModel.platform)) {
        openModal(
          t('dataModels.createDataModel.replaceDesc'),
          t('dataModels.createDataModel.replaceTitle'),
          () => updateDataModelMutation.mutate(updatedPayload),
          'replace'
        );
      } else {
        updateDataModelMutation.mutate(updatedPayload);
      }
    }
  };

  const updateDataModelMutation = useMutation({
    mutationFn: (data: UpdatedDataModelPayload) => updateDataModel(data),
    onSuccess: async () => {
      open({
        title: t('dataModels.configureDataModel.saveChangesTitile'),
        content: <p>{t('dataModels.configureDataModel.saveChangesDesc')}</p>,
        footer: (
          <div className="flex-grid">
            <Button
              appearance={ButtonAppearanceTypes.SECONDARY}
              onClick={() => {
                navigate(0);
                close();
              }}
            >
              {t('global.cancel')}
            </Button>{' '}
            <Button
              onClick={() => {
                navigate(0);
                close();
              }}
            >
              {t('dataModels.createDataModel.viewAll')}
            </Button>
          </div>
        ),
      });
    },
    onError: () => {
      open({
        title: t('dataModels.configureDataModel.updateErrorTitile'),
        content: <p>{t('dataModels.configureDataModel.updateErrorDesc')}</p>,
      });
    },
  });

  const handleDelete = () => {
    if (
      dataModel.platform === Platform.JIRA ||
      dataModel.platform === Platform.OUTLOOK
    ) {
      open({
        title: t('dataModels.configureDataModel.deleteErrorTitle'),
        content: <p>{t('dataModels.configureDataModel.deleteErrorDesc')}</p>,
        footer: (
          <div className="flex-grid">
            <Button
              appearance={ButtonAppearanceTypes.SECONDARY}
              onClick={close}
            >
              {t('global.cancel')}
            </Button>
          </div>
        ),
      });
    } else {
      openModal(
        t('dataModels.configureDataModel.deleteConfirmationDesc'),
        t('dataModels.configureDataModel.deleteConfirmation'),
        () => deleteDataModelMutation.mutate(dataModel.modelId),
        'delete'
      );

    }
  };

  const deleteDataModelMutation = useMutation({
    mutationFn: (modelId: number) => deleteDataModel(modelId),
    onSuccess: async (response) => {
      close();
      navigate(0);
    },
    onError: () => {
      open({
        title: t('dataModels.configureDataModel.deleteModalErrorTitle'),
        content: (
          <p>{t('dataModels.configureDataModel.deleteModalErrorDesc')}</p>
        ),
      });
    },
  });

  const retrainDataModelMutation = useMutation({
    mutationFn: (modelId: number) => retrainDataModel(modelId),
    onSuccess: async () => {
      close();
      navigate(0);
      setModalOpen(false)
    },
    onError: () => {
      open({
        title: t('dataModels.configureDataModel.retrainDataModalErrorTitle'),
        content: (
          <p>{t('dataModels.configureDataModel.retrainDataModalErrorDesc')}</p>
        ),
      });
    },
  });

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
                  retrainDataModelMutation.mutate(dataModel.modelId);
                }}
              >
                {t('dataModels.configureDataModel.retrain')}
              </Button>
            </div>
          </div>
        </Card>

        {isLoading ? (
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
          disabled={deleteDataModelMutation.isLoading}
          showLoadingIcon={deleteDataModelMutation.isLoading}
          onClick={() => handleDelete()}
        >
          {t('dataModels.configureDataModel.deleteModal')}
        </Button>
        <Button
          disabled={!dataModel.dgId || dataModel.dgId === 0}
          onClick={() =>
            openModal(
              t('dataModels.configureDataModel.confirmRetrainDesc'),
              t('dataModels.configureDataModel.retrain'),
              () => retrainDataModelMutation.mutate(dataModel.modelId),
              'retrain'
            )
          }
        >
          {t('dataModels.configureDataModel.retrain')}
        </Button>
        <Button
          disabled={updateDataModelMutation.isLoading}
          showLoadingIcon={updateDataModelMutation.isLoading}
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
                disabled={retrainDataModelMutation.isLoading || !dataModel.dgId || dataModel.dgId === 0}
                showLoadingIcon={retrainDataModelMutation.isLoading}
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
            ) : (
              <Button
                disabled={updateDataModelMutation.isLoading}
                showLoadingIcon={updateDataModelMutation.isLoading}
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