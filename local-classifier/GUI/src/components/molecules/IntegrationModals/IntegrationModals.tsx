import {
  INTEGRATION_MODALS,
  INTEGRATION_OPERATIONS,
} from 'enums/integrationEnums';
import React from 'react';
import { Button, Dialog } from 'components';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { togglePlatform } from 'services/integration';
import { useTranslation } from 'react-i18next';
import { OperationConfig } from 'types/integration';
import { integrationQueryKeys } from 'utils/queryKeys';

const IntegrationModals = ({
  modalType,
  isModalOpen,
  setIsModalOpen,
  channel,
  setModalType,
}: {
  modalType: INTEGRATION_MODALS;
  isModalOpen: boolean;
  setIsModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  channel?: string;
  setModalType: React.Dispatch<React.SetStateAction<INTEGRATION_MODALS>>;
}) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const platformEnableMutation = useMutation({
    mutationFn: (data: OperationConfig) => togglePlatform(data),
    onSuccess: async (data) => {
      if (data.response.operation_status === 'success') {
        setModalType(INTEGRATION_MODALS.INTEGRATION_SUCCESS);
        await queryClient.invalidateQueries(
          integrationQueryKeys.INTEGRATION_STATUS()
        );
      } else {
        setModalType(INTEGRATION_MODALS.INTEGRATION_ERROR);
      }
    },
    onError: () => {
      setModalType(INTEGRATION_MODALS.INTEGRATION_ERROR);
    },
  });

  const platformDisableMutation = useMutation({
    mutationFn: (data: OperationConfig) => togglePlatform(data),
    onSuccess: async (data) => {
      if (data.response.operation_status === 'success') {
        await queryClient.invalidateQueries(
          integrationQueryKeys.INTEGRATION_STATUS()
        );
        setIsModalOpen(false);
      } else {
        setModalType(INTEGRATION_MODALS.DISCONNECT_ERROR);
      }
    },
    onError: () => {
      setModalType(INTEGRATION_MODALS.DISCONNECT_ERROR);
    },
  });
  return (
    <>
      {modalType === INTEGRATION_MODALS.INTEGRATION_SUCCESS && (
        <Dialog
          onClose={() => setIsModalOpen(false)}
          isOpen={isModalOpen}
          title={t('integration.integrationSuccessTitle')}
        >
          <div className="form-container">
            {t('integration.integrationSuccessDesc', { channel })}
          </div>
        </Dialog>
      )}
      {modalType === INTEGRATION_MODALS.INTEGRATION_ERROR && (
        <Dialog
          onClose={() => setIsModalOpen(false)}
          isOpen={isModalOpen}
          title={t('integration.integrationErrorTitle')}
        >
          <div className="form-container">
            {t('integration.integrationErrorDesc', { channel })}
          </div>
        </Dialog>
      )}
      {modalType === INTEGRATION_MODALS.DISCONNECT_CONFIRMATION && (
        <Dialog
          onClose={() => setIsModalOpen(false)}
          isOpen={isModalOpen}
          title={t('integration.confirmationModalTitle')}
          footer={
            <div className="footer-button-wrapper">
              <Button
                appearance="secondary"
                onClick={() => setIsModalOpen(false)}
              >
                {t('global.cancel')}
              </Button>
              <Button
                appearance="error"
                onClick={() => {
                  platformDisableMutation.mutate({
                    operation: INTEGRATION_OPERATIONS.DISABLE,
                    platform: channel?.toLowerCase(),
                  });
                }}
                disabled={platformDisableMutation.isLoading}
                showLoadingIcon={platformDisableMutation.isLoading}
              >
                {t('global.disconnect')}
              </Button>
            </div>
          }
        >
          <div className="form-container">
            {t('integration.disconnectConfirmationModalDesc', { channel })}
          </div>
        </Dialog>
      )}
      {modalType === INTEGRATION_MODALS.CONNECT_CONFIRMATION && (
        <Dialog
          onClose={() => setIsModalOpen(false)}
          isOpen={isModalOpen}
          title={t('integration.confirmationModalTitle')}
          footer={
            <div className="footer-button-wrapper">
              <Button
                appearance="secondary"
                onClick={() => setIsModalOpen(false)}
              >
                {t('global.cancel')}
              </Button>
              <Button
                appearance="primary"
                onClick={() => {
                  platformEnableMutation.mutate({
                    operation: INTEGRATION_OPERATIONS.ENABLE,
                    platform: channel?.toLowerCase(),
                  });
                }}
                disabled={platformEnableMutation.isLoading}
                showLoadingIcon={platformEnableMutation.isLoading}
              >
                {t('global.connect')}
              </Button>
            </div>
          }
        >
          <div className="form-container">
            {t('integration.connectConfirmationModalDesc', { channel })}
          </div>
        </Dialog>
      )}
      {modalType === INTEGRATION_MODALS.DISCONNECT_ERROR && (
        <Dialog
          onClose={() => setIsModalOpen(false)}
          isOpen={isModalOpen}
          title={t('integration.disconnectErrorTitle')}
        >
          <div className="form-container">
            {t('integration.disconnectErrorDesc', { channel })}
          </div>
        </Dialog>
      )}
    </>
  );
};

export default IntegrationModals;
