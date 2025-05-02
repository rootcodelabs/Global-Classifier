import { FC, useMemo, useState } from 'react';
import { Button, DataTable } from '../../components';
import {
  PaginationState,
  Row,
  SortingState,
  createColumnHelper,
} from '@tanstack/react-table';
import { User } from '../../types/user';
import './UserManagement.scss';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import apiDev from 'services/api-dev';
import UserModal from './UserModal';
import { userManagementQueryKeys } from 'utils/queryKeys';
import { userManagementEndpoints } from 'utils/endpoints';
import { ButtonAppearanceTypes } from 'enums/commonEnums';
import SkeletonTable from 'components/molecules/TableSkeleton/TableSkeleton';
import CircularSpinner from 'components/molecules/CircularSpinner/CircularSpinner';
import ActionButtons from 'components/molecules/UserManagementActionButtons/UserManagementActionButtons';

const UserManagement: FC = () => {
  const columnHelper = createColumnHelper<User>();
  const [newUserModal, setNewUserModal] = useState(false);
  const [editableRow, setEditableRow] = useState<User | null>(null);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  });
  const [sorting, setSorting] = useState<SortingState>([]);
  const { t } = useTranslation();

  const getSortString = (length: number) => {
    if (length === 0) return 'name asc';
    else
      return `${sorting[0]?.id} ${
        sorting[0]?.desc ? t('global.desc') : t('global.asc')
      }`;
  };
  const fetchUsers = async (
    pagination: PaginationState,
    sorting: SortingState
  ) => {
    const sort = getSortString(sorting?.length);    
    const { data } = await apiDev.post(userManagementEndpoints.FETCH_USERS(), {
      page: pagination?.pageIndex + 1,
      page_size: pagination?.pageSize,
      sorting: sort,
    });
    return data?.response ?? [];
  };

  const { data: users, isLoading } = useQuery({
    queryKey: userManagementQueryKeys.getAllEmployees(pagination, sorting),
    queryFn: () => fetchUsers(pagination, sorting),
    onSuccess: (data) => {
      setTotalPages(data[0]?.totalPages);
    },
  });

  const usersColumns = useMemo(
    () => [
      columnHelper.accessor(
        (row: User) => `${row?.firstName ?? ''} ${row?.lastName ?? ''}`,
        {
          id: 'name',
          header: t('userManagement.table.fullName') ?? '',
        }
      ),
      columnHelper.accessor('useridcode', {
        id :"idCode",
        header: t('userManagement.table.personalId') ?? '',
      }),
      columnHelper.accessor('csaTitle', {
        header: t('userManagement.table.title') ?? '',
      }),
      columnHelper.accessor(
        (data: User) => {
          const output: string[] = [];
          data.authorities?.forEach((role) => output.push(t(`roles.${role}`)));
          return output;
        },
        {
          header: t('userManagement.table.role') ?? '',
          cell: (props) => props.getValue<string[]>().join(', '),
          filterFn: (row: Row<User>, _, filterValue: string) => {
            const rowAuthorities = row.original.authorities.map((role) =>
              t(`roles.${role}`)
            );
            return rowAuthorities.some((word) =>
              word.toLowerCase().includes(filterValue.toLowerCase())
            );
          },
        }
      ),
      columnHelper.accessor('csaEmail', {
        header: t('userManagement.table.email') ?? '',
      }),
      columnHelper.display({
        id: 'actions',
        header: () => (
          <div className="table-header">
            {t('userManagement.table.actions') ?? ''}
          </div>
        ),
        cell: (props) => (
          <ActionButtons
            row={props?.row?.original}
            setEditableRow={setEditableRow}
          />
        ),
        meta: {
          size: '1%',
        },
      }),
    ],
    [t]
  );

  if (isLoading) return <CircularSpinner />;

  return (
    <div>
      <div className="container">
        <div className="title_container">
          <div className="title">{t('userManagement.title')}</div>
          <Button
            appearance={ButtonAppearanceTypes.PRIMARY}
            size="m"
            onClick={() => {
              setNewUserModal(true);
            }}
          >
            {t('userManagement.addUserButton')}
          </Button>
        </div>
        <div>
          {!isLoading && (
            <DataTable
              data={users}
              columns={usersColumns}
              sortable
              filterable
              pagination={pagination}
              setPagination={(state: PaginationState) => {
                if (
                  state?.pageIndex === pagination?.pageIndex &&
                  state?.pageSize === pagination?.pageSize
                )
                  return;
                setPagination(state);
                fetchUsers(state, sorting);
              }}
              sorting={sorting}
              setSorting={(state: SortingState) => {
                setSorting(state);
                fetchUsers(pagination, state);
              }}
              pagesCount={totalPages}
              isClientSide={false}
            />
          )}

          {isLoading && <SkeletonTable rowCount={5} />}

          {newUserModal && (
            <UserModal
              isModalOpen={newUserModal}
              onClose={() => setNewUserModal(false)}
            />
          )}

          {editableRow && (
            <UserModal
              user={editableRow}
              onClose={() => setEditableRow(null)}
              isModalOpen={editableRow !== null}
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default UserManagement;
