import { CellContext, createColumnHelper } from '@tanstack/react-table';

export const generateDynamicColumns = (
  columnsData: string[],
  editView?: (props: CellContext<any, unknown>) => JSX.Element,
  deleteView?: (props: CellContext<any, unknown>) => JSX.Element
) => {
  const columnHelper = createColumnHelper<any>(); // Specify the type for better type checking
  const dynamicColumns = columnsData?.map((col) => {
    return columnHelper.accessor(col, {
      header: col ?? '',
      id: col,
    });
  });

  const staticColumns = [];

  if (editView) {
    staticColumns.push(
      columnHelper.display({
        id: 'edit',
        cell: editView,
        meta: {
          size: '1%',
        },
      })
    );
  }

  if (deleteView) {
    staticColumns.push(
      columnHelper.display({
        id: 'delete',
        cell: deleteView,
        meta: {
          size: '1%',
        },
      })
    );
  }

  if (dynamicColumns) return [...dynamicColumns, ...staticColumns];
  else return staticColumns;
};
