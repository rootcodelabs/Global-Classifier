import { FC } from 'react';
import Button from 'components/Button';
import Icon from 'components/Icon';
import { useTranslation } from 'react-i18next';
import { MdOutlineDeleteOutline, MdOutlineEdit } from 'react-icons/md';
import { User } from 'types/user';
import { ButtonAppearanceTypes, ToastTypes } from 'enums/commonEnums';
import { useDialog } from 'hooks/useDialog';
import { deleteUser } from 'services/users';
import { userManagementQueryKeys } from 'utils/queryKeys';
import { useToast } from 'hooks/useToast';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';

const ActionButtons: FC<{
  row: User;
  setEditableRow: React.Dispatch<React.SetStateAction<User | null>>;
}> = ({ row, setEditableRow }) => {
  const { t } = useTranslation();
  const { open, close } = useDialog();
  const toast = useToast();
  const queryClient = useQueryClient();

  const deleteUserMutation = useMutation({
    mutationFn: ({ id }: { id: string | number }) => deleteUser(id),
    onSuccess: async () => {
      close();
      await queryClient.invalidateQueries(
        userManagementQueryKeys.getAllEmployees()
      );
      toast.open({
        type: ToastTypes.SUCCESS,
        title: t('global.notification'),
        message: t('toast.success.userDeleted'),
      });
    },
    onError: (error: AxiosError) => {
      toast.open({
        type: ToastTypes.ERROR,
        title: t('global.notificationError'),
        message: error?.message ?? '',
      });
    },
  });

  return (
    <div className="action-button-container">
      <Button
        appearance={ButtonAppearanceTypes.TEXT}
        onClick={() => setEditableRow(row)}
      >
        <Icon icon={<MdOutlineEdit />} />
        {t('global.change')}
      </Button>
      <Button
        appearance={ButtonAppearanceTypes.TEXT}
        onClick={async () => {
          open({
            title: t('userManagement.addUser.deleteUserModalTitle') ?? '',
            content: <p>{t('userManagement.addUser.deleteUserModalDesc')}</p>,
            footer: (
              <div className="button-wrapper">
                <Button
                  appearance={ButtonAppearanceTypes.SECONDARY}
                  onClick={() => {
                    close();
                  }}
                >
                  {t('global.cancel')}
                </Button>
                <Button
                  appearance={ButtonAppearanceTypes.ERROR}
                  onClick={() =>
                    deleteUserMutation.mutate({ id: row.useridcode })
                  }
                >
                  {t('global.confirm')}
                </Button>
              </div>
            ),
          });
        }}
      >
        <Icon icon={<MdOutlineDeleteOutline />} />
        {t('global.delete')}
      </Button>
    </div>
  );
};

export default ActionButtons;
