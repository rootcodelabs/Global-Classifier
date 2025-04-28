import {
  CreateDatasetGroupModals,
  ValidationErrorTypes,
} from 'enums/datasetEnums';
import { Button, Dialog } from 'components';
import { ButtonAppearanceTypes } from 'enums/commonEnums';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

const CreateDatasetGroupModalController = ({
  modalType,
  isModalOpen,
  setIsModalOpen,
  validationErrorType,
}: {
  modalType: CreateDatasetGroupModals;
  isModalOpen: boolean;
  setIsModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  validationErrorType?: ValidationErrorTypes;
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  return (
    <>
      {modalType === CreateDatasetGroupModals.VALIDATION_ERROR && (
        <Dialog
          isOpen={isModalOpen}
          title={
            validationErrorType === ValidationErrorTypes.VALIDATION_CRITERIA
              ? t('datasetGroups.modals.columnInsufficientHeader')
              : t('datasetGroups.modals.classsesInsufficientHeader')
          }
          footer={
            <div className="footer-button-wrapper">
              <Button
                appearance={ButtonAppearanceTypes.SECONDARY}
                onClick={() => setIsModalOpen(false)}
              >
                {t('global.cancel')}
              </Button>
              <Button onClick={() => setIsModalOpen(false)}>
                {t('datasetGroups.createDataset.addNowButton')}
              </Button>
            </div>
          }
          onClose={() => setIsModalOpen(false)}
        >
          {validationErrorType === ValidationErrorTypes.VALIDATION_CRITERIA
            ? t('datasetGroups.modals.columnInsufficientDescription')
            : t('datasetGroups.modals.classsesInsufficientDescription')}
        </Dialog>
      )}
      {modalType === CreateDatasetGroupModals.SUCCESS && (
        <Dialog
          isOpen={isModalOpen}
          title={t('datasetGroups.modals.createDatasetSuccessTitle')}
          footer={
            <div className="footer-button-wrapper">
              <Button
                appearance={ButtonAppearanceTypes.SECONDARY}
                onClick={() => setIsModalOpen(false)}
              >
                {t('global.cancel')}
              </Button>
              <Button onClick={() => navigate('/dataset-groups')}>
                {t('datasetGroups.modals.navigateDetailedViewButton')}
              </Button>
            </div>
          }
          onClose={() => setIsModalOpen(false)}
        >
          {t('datasetGroups.modals.createDatasetSucceessDesc')}
        </Dialog>
      )}
    </>
  );
};

export default CreateDatasetGroupModalController;
