import React, { FC, PropsWithChildren } from 'react';
import dataTypes from '../../../config/dataTypesConfig.json';
import { MdAdd, MdDelete } from 'react-icons/md';
import { FormCheckbox, FormInput, FormSelect } from 'components/FormElements';
import { ValidationRule } from 'types/datasetGroups';
import { Link } from 'react-router-dom';
import { isFieldNameExisting } from 'utils/datasetGroupsUtils';
import { v4 as uuidv4 } from 'uuid';
import { useTranslation } from 'react-i18next';
import './RowViewStyle.scss';

type ValidationRulesProps = {
  validationRules?: ValidationRule[];
  setValidationRules: React.Dispatch<
    React.SetStateAction<ValidationRule[] | undefined>
  >;
  validationRuleError?: boolean;
  setValidationRuleError: React.Dispatch<React.SetStateAction<boolean>>;
};

const ValidationCriteriaRowsView: FC<
  PropsWithChildren<ValidationRulesProps>
> = ({
  validationRules,
  setValidationRules,
  setValidationRuleError,
  validationRuleError,
}) => {
  const { t } = useTranslation();
  const setIsDataClass = (id: string | number, isDataClass: boolean) => {
    const updatedItems = validationRules?.map((item) =>
      item.id === id ? { ...item, isDataClass: !isDataClass } : item
    );
    updatedItems && setValidationRules(updatedItems);
  };

  const changeName = (id: number | string, newValue: string) => {
    setValidationRules((prevData) =>
      prevData?.map((item) =>
        item.id === id ? { ...item, fieldName: newValue } : item
      )
    );

    if (
      isFieldNameExisting(validationRules, newValue)) {
      setValidationRuleError(true);
    }
  };

  const changeDataType = (id: number | string, value: string) => {
    const updatedItems = validationRules?.map((item) =>
      item.id === id ? { ...item, dataType: value } : item
    );
    setValidationRules(updatedItems);
  };

  const addNewClass = () => {
    setValidationRuleError(false);
    const updatedItems = [
      ...(validationRules ?? []),
      { id: uuidv4(), fieldName: '', dataType: '', isDataClass: false },
    ];

    setValidationRules(updatedItems);
  };

  const deleteItem = (idToDelete: number | string) => {
    const updatedItems = validationRules?.filter(
      (item) => item.id !== idToDelete
    );
    setValidationRules(updatedItems);
  };

  const getErrorMessage = (item: ValidationRule) => {
    console.log(validationRuleError);

    if (validationRuleError) {
      if (!item.fieldName) {
        return t('datasetGroups.detailedView.fieldName');
      }
      if (item.fieldName.toLowerCase() === 'rowid') {
        return t('datasetGroups.detailedView.fieldNameError', {
          name: item.fieldName,
        });
      }
      if (isFieldNameExisting(validationRules, item.fieldName)) {
        return t('datasetGroups.detailedView.fieldNameExist', {
          name: item.fieldName,
        });
      }
    }
    return '';
  };

  const getBackgroundColor = (index: number) => {
    if (index % 2 === 1) return '#F9F9F9';
    else return '#FFFFFF';
  };

  return (
    <div className="m--16">
      {validationRules?.map((item, index) => (
        <div
          key={item.id}
          className="rowViewContentWrapper"
          style={{
            background: getBackgroundColor(index),
          }}
        >
          <FormInput
            label="Field Name"
            placeholder="Enter Field Name"
            name={`fieldName ${index}`}
            defaultValue={item.fieldName}
            onBlur={(e) => changeName(item.id, e.target.value)}
            error={getErrorMessage(item)}
          />
          <FormSelect
            label="Data Type"
            name={`dataType ${index}`}
            options={dataTypes}
            defaultValue={item.dataType}
            onSelectionChange={(selection) =>
              changeDataType(item.id, (selection?.value as string) ?? '')
            }
            error={
              validationRuleError && !item.dataType
                ? t('datasetGroups.detailedView.selectDataType') ?? ''
                : ''
            }
          />
          <div className="rowViewButtonWrapper">
            <Link
              to={''}
              onClick={() => addNewClass()}
              className="rowViewButton"
            >
              <MdAdd />
              {t('global.add')}
            </Link>
            <Link
              to={''}
              onClick={() => deleteItem(item.id)}
              className="rowViewButton"
            >
              <MdDelete />
              {t('global.delete')}
            </Link>
            <FormCheckbox
              label=""
              item={{
                label: 'Data Class',
                value: 'active',
              }}
              name="dataClass"
              checked={item.isDataClass}
              onChange={() => setIsDataClass(item.id, item.isDataClass)}
              style={{ width: '150px' }}
            />
          </div>
        </div>
      ))}
    </div>
  );
};

export default ValidationCriteriaRowsView;
