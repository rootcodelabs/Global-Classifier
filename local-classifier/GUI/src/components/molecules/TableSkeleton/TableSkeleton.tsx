import React from 'react';
import './SkeletonTable.scss';

interface SkeletonTableProps {
  rowCount: number;
}

const SkeletonTable: React.FC<SkeletonTableProps> = ({ rowCount }) => {
  const skeletonRows = Array.from({ length: rowCount }, (_, index) => (
    <tr key={index}>
      <td>
        <div className="skeleton"></div>
      </td>
    </tr>
  ));

  return (
    <table className="table">
      <tbody>{skeletonRows}</tbody>
    </table>
  );
};

export default SkeletonTable;