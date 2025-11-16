import { FC, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from 'components';
import { Link, useNavigate } from 'react-router-dom';
import './DataModels.scss';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useDialog } from 'hooks/useDialog';
import BackArrowButton from 'assets/BackArrowButton';
import DataModelForm from 'components/molecules/DataModelForm';
import { ButtonAppearanceTypes } from 'enums/commonEnums';
import {
  DataModel,
  ErrorsType,
} from 'types/dataModels';
import { createDataModel, getProductionDataModel } from 'services/datamodels';
import { dataModelsQueryKeys } from 'utils/queryKeys';
import { getAllDatasetVersions } from 'services/datasets';

const CreateDataModel: FC = () => {
  const { t } = useTranslation();
  const { open, close } = useDialog();
  const navigate = useNavigate();

  const [dataModel, setDataModel] = useState<Partial<DataModel>>({
    modelName: '',
    datasetId: 0,
    baseModels: [],
    deploymentEnvironment: '',
    version: 'V1.0',
  });

  const { data: prodDataModel, isLoading: isProdDataModelLoading } = useQuery({
    queryKey: dataModelsQueryKeys.GET_PROD_DATA_MODEL(),
    queryFn: () => getProductionDataModel(),
  });

  const { data: datasetVersions } = useQuery({
    queryKey: dataModelsQueryKeys.DATA_MODEL_DEPLOYMENT_ENVIRONMENTS(),
    queryFn: () => getAllDatasetVersions(),
  });

  const handleDataModelAttributesChange = (name: string, value: string) => {
    // Update version when dataset is changed
    if (name === 'datasetId' && value && datasetVersions) {
      const selectedDataset = datasetVersions.find(
        (dataset: any) => dataset.id.toString() === value
      );
      if (selectedDataset?.version) {
        setDataModel((prevDataModel) => ({
          ...prevDataModel,
          [name]: value,
          version: selectedDataset.version,
        }));
        
        // Clear datasetId error
        setErrors((prevErrors) => {
          const updatedErrors = { ...prevErrors };
          delete updatedErrors.datasetId;
          return updatedErrors;
        });
        return; // Early return to avoid the second setDataModel call
      }
    }

    // Default case - just update the field
    setDataModel((prevFilters) => ({
      ...prevFilters,
      [name]: value,
    }));

    setErrors((prevErrors) => {
      const updatedErrors = { ...prevErrors };

      if (name === 'modelName' && value !== '') {
        delete updatedErrors.modelName;
      }
      if (name === 'baseModels' && value !== '') {
        delete updatedErrors.baseModels;
      }
      if (name === 'deploymentEnvironment' && value !== '') {
        delete updatedErrors.deploymentEnvironment;
      }
      if (name === 'datasetId') {
        delete updatedErrors.datasetId;
      }

      return updatedErrors;
    });
  };

  const [errors, setErrors] = useState<ErrorsType>({
    modelName: '',
    datasetId: '',
    baseModels: '',
    deploymentEnvironment: '',
  });

  const mutation = useMutation({
    mutationFn: createDataModel,
    onSuccess: () => {
      open({
        title: t('dataModels.createDataModel.successTitle'),
        content: t('dataModels.createDataModel.successDesc'),
        footer: (<div className='flex-grid'><Button appearance={ButtonAppearanceTypes.SECONDARY} onClick={() => { close() }}>Close</Button><Button onClick={() => { navigate('/data-models'), close() }}>View all Data Models</Button></div>)
      });

    },
    onError: () => {
      open({
        title: t('dataModels.createDataModel.errorTitle'),
        content: t('dataModels.createDataModel.errorDesc'),
      });
    },
  });

  const handleCreate = () => {
    // Parse version correctly - version format is "V1.0"
    const versionParts = dataModel?.version?.split('.');
    const majorVersion = versionParts?.[0]?.substring(1); // Remove 'V' prefix
    const minorVersion = versionParts?.[1];

    const paylod = {
      modelName: dataModel.modelName ?? "",
      deploymentEnv: dataModel.deploymentEnvironment ?? "",
      baseModels: dataModel.baseModels ?? [],
      connectedDsId: Number(dataModel.datasetId) ?? 0,
      connectedDsMajorVersion: Number(majorVersion) ?? 1,
      connectedDsMinorVersion: Number(minorVersion) ?? 0,
    }

    if (prodDataModel && dataModel.deploymentEnvironment === "production") {
      open({
        title: t('dataModels.createDataModel.replaceTitle'),
        content: t('dataModels.createDataModel.replaceDesc'),
        footer: (<div className='flex-grid'><Button appearance={ButtonAppearanceTypes.SECONDARY} onClick={() => { close() }}>Close</Button><Button onClick={() => mutation.mutate(paylod)}>Replace</Button></div>)
      });
    } else {
      mutation.mutate(paylod);
    }
  };

  const isCreateDisabled = () => {
    return (
      !dataModel.modelName ||
      dataModel.modelName.length > 256 ||
      !dataModel.datasetId ||
      !dataModel.baseModels ||
      (Array.isArray(dataModel.baseModels) && dataModel.baseModels.length === 0) ||
      !dataModel.deploymentEnvironment
    );
  };

  return (
    <div>
      <div className="container">
        <div className="title_container">
          <div className="flex-grid">
            <Link to={'/data-models'}>
              <BackArrowButton />
            </Link>
            <div className="title">{t('dataModels.createDataModel.title')}</div>
          </div>
        </div>
        <DataModelForm
          errors={errors}
          dataModel={dataModel}
          handleChange={handleDataModelAttributesChange}
          type="create"
          datasetVersions={datasetVersions}
        />
      </div>
      <div className="flex data-model-buttons">
        <Button onClick={() => handleCreate()} 
        disabled={isCreateDisabled() || mutation.isLoading} 
        appearance={ButtonAppearanceTypes.PRIMARY}
        showLoadingIcon={mutation.isLoading}>
          {t('dataModels.createDataModel.title')}
        </Button>
        <Button appearance="secondary" onClick={() => navigate('/data-models')}>
          {t('global.cancel')}
        </Button>
      </div>
    </div>
  );
};

export default CreateDataModel;
