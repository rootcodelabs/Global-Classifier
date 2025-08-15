import React, { FC, useState, MouseEvent } from 'react';
import { Column, Table } from '@tanstack/react-table';
import { useTranslation } from 'react-i18next';
import { MdOutlineFilterList } from 'react-icons/md';

import { Icon } from 'components';
import useDocumentEscapeListener from 'hooks/useDocumentEscapeListener';

type DropdownFilterProps = {
  column: Column<any, unknown>;
  table: Table<any>;
  options: { label: string; value: string | number }[];
  onSelect: (value: string | number) => void; // <-- Add this prop
};

const DropdownFilter: FC<DropdownFilterProps> = ({ column, table, options, onSelect }) => {
  const { t } = useTranslation();
  const [filterOpen, setFilterOpen] = useState(false);
  const [selectedValue, setSelectedValue] = useState<string | number>('');

  useDocumentEscapeListener(() => setFilterOpen(false));

  const handleFilterToggle = (e: MouseEvent) => {
    e.stopPropagation();
    setFilterOpen(!filterOpen);
  };

  const handleSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedValue(e.target.value);
    setFilterOpen(false);
    onSelect(e.target.value); // <-- Call the callback with the selected value
  };

  return (
    <>
      <button onClick={handleFilterToggle}>
        <Icon icon={<MdOutlineFilterList fontSize={16} />} size="medium" />
      </button>
      {filterOpen && (
        <div className="data-table__dropdown_filter">
          <select value={selectedValue} onChange={handleSelect}>
            <option value="">{t('global.select') || 'Select option'}</option>
            {options.map(opt => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      )}
    </>
  );
};

export default DropdownFilter;