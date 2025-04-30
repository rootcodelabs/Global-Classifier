import {
  forwardRef,
  ReactNode,
  SelectHTMLAttributes,
  useId,
  useState,
  useEffect,
} from 'react';
import { useSelect } from 'downshift';
import clsx from 'clsx';
import { useTranslation } from 'react-i18next';
import { MdArrowDropDown } from 'react-icons/md';

import { Icon } from 'components';
import './FormSelect.scss';
import { ControllerRenderProps } from 'react-hook-form';

type FormSelectOption = {
  label: string;
  value: string | { name: string; id: string };
};

type FormSelectProps = Partial<ControllerRenderProps> &
  SelectHTMLAttributes<HTMLSelectElement> & {
    label: ReactNode;
    name: string;
    placeholder?: string;
    hideLabel?: boolean;
    direction?: 'down' | 'up';
    options: FormSelectOption[];
    onSelectionChange?: (selection: FormSelectOption | null) => void;
    error?: string;
    defaultValue?: string | { name: string; id: string } | number;
  };

const itemToString = (item: FormSelectOption | null) => {
  return item ? item.value.toString() : '';
};

const FormSelect = forwardRef<HTMLSelectElement, FormSelectProps>(
  (
    {
      label,
      hideLabel,
      direction = 'down',
      options,
      disabled,
      placeholder,
      defaultValue,
      onSelectionChange,
      error,
      ...rest
    },
    ref
  ) => {
    const id = useId();
    const { t } = useTranslation();

    const [selectedItem, setSelectedItem] = useState<FormSelectOption | null>(
      options?.find((o) => o.value === defaultValue) ||
        options?.find(
          (o) => typeof o.value === 'object' && o.value?.name === defaultValue
        ) ||
        null
    );

    useEffect(() => {
      const newSelectedItem =
        options?.find((o) => o.value === defaultValue) ||
        options?.find(
          (o) => typeof o.value === 'object' && o.value?.name === defaultValue
        ) ||
        null;
        setSelectedItem(newSelectedItem);
    }, [defaultValue, options]);

    const {
      isOpen,
      getToggleButtonProps,
      getLabelProps,
      getMenuProps,
      highlightedIndex,
      getItemProps,
    } = useSelect({
      id,
      items: options,
      itemToString,
      selectedItem,
      onSelectedItemChange: ({ selectedItem: newSelectedItem }) => {
        setSelectedItem(newSelectedItem ?? null);
        if (onSelectionChange) onSelectionChange(newSelectedItem ?? null);
      },
    });

    const selectClasses = clsx('select', disabled && 'select--disabled');

    const placeholderValue =
      placeholder || t('datasetGroups.createDataset.selectPlaceholder');

    return (
      <div className={selectClasses} style={rest.style}>
        {label && !hideLabel && (
          <label htmlFor={id} className="select__label" {...getLabelProps()}>
            {label}
          </label>
        )}
        <div className="select__wrapper">
          <div
            className={`select__trigger ${
              error ? `select__error` : `select__default`
            }`}
            {...getToggleButtonProps()}
          >
            {selectedItem?.label ?? placeholderValue}
            <Icon
              label="Dropdown icon"
              size="medium"
              icon={<MdArrowDropDown color="#5D6071" />}
            />
          </div>
          <ul
            ref={ref}
            className={
              direction === 'down' ? 'select__menu' : 'select__menu_up'
            }
            {...getMenuProps()}
          >
            {isOpen &&
              options.map((item, index) => (
                <li
                  className={clsx('select__option', {
                    'select__option--selected': highlightedIndex === index,
                  })}
                  key={`${item.value}${index}`}
                  {...getItemProps({ item, index })}
                >
                  {item.label}
                </li>
              ))}
          </ul>
          {error && <p className="input__inline_error">{error}</p>}
        </div>
      </div>
    );
  }
);

export default FormSelect;
