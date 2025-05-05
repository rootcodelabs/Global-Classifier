import React, { useCallback } from 'react';
import { useDrag, useDrop } from 'react-dnd';
import { MdDehaze, MdDeleteOutline } from 'react-icons/md';
import Card from 'components/Card';
import { FormCheckbox, FormInput, FormSelect } from 'components/FormElements';
import { ValidationRule } from 'types/datasetGroups';
import { Link } from 'react-router-dom';
import { isFieldNameExisting } from 'utils/datasetGroupsUtils';
import './DragableItemStyle.scss';
import { useTranslation } from 'react-i18next';
import useOptionLists from 'hooks/useOptionLists';

const ItemTypes = {
  ITEM: 'item',
};

const DraggableItem = ({
  item,
  index,
  moveItem,
  setValidationRules,
  validationRuleError,
  validationRules,
  setValidationRuleError,
}: {
  item: ValidationRule;
  index: number;
  moveItem: (fromIndex: number, toIndex: number) => void;
  validationRules?: ValidationRule[];
  setValidationRules: React.Dispatch<React.SetStateAction<ValidationRule[]>>;
  validationRuleError?: boolean;
  setValidationRuleError: React.Dispatch<React.SetStateAction<boolean>>;
}) => {
  const { t } = useTranslation();
  const [, ref] = useDrag({
    type: ItemTypes.ITEM,
    item: { index },
  });

  const { dataTypesConfigs: dataTypes } = useOptionLists();

  const [, drop] = useDrop({
    accept: ItemTypes.ITEM,
    hover: (draggedItem: { index: number }) => {
      if (draggedItem.index !== index) {
        moveItem(draggedItem.index, index);
        draggedItem.index = index;
      }
    },
  });

  const deleteItem = (idToDelete: string | number) => {
    const updatedItems = validationRules?.filter(
      (item) => item?.id !== idToDelete
    );
    updatedItems && setValidationRules(updatedItems);
  };

  const setIsDataClass = (id: string | number, isDataClass: boolean) => {
    const updatedItems = validationRules?.map((item) =>
      item.id === id ? { ...item, isDataClass: !isDataClass } : item
    );
    updatedItems && setValidationRules(updatedItems);
  };

  const handleChange = useCallback((id: string | number, newValue: string) => {
    setValidationRules((prevData) =>
      prevData.map((item) =>
        item.id === id ? { ...item, fieldName: newValue } : item
      )
    );
  }, []);

  const changeDataType = (id: string | number, value: string) => {
    const updatedItems = validationRules?.map((item) =>
      item.id === id ? { ...item, dataType: value } : item
    );
    updatedItems && setValidationRules(updatedItems);
  };

  const getErrorMessage = (item: ValidationRule) => {    
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

  return (
    <div ref={(node) => ref(drop(node))}>
      <Card>
        <div className="dragabbleCardContainer">
          <FormInput
            label={t('datasetGroups.createDataset.fieldName')}
            placeholder="Enter Field Name"
            name={`fieldName ${index}`}
            defaultValue={item.fieldName}
            onBlur={(e) => handleChange(item.id, e.target.value)}
            error={getErrorMessage(item)}
            aria-autocomplete="none"
          />
          <FormSelect
            label={t('datasetGroups.createDataset.datasetType')}
            name={`dataType ${index}`}
            options={dataTypes}
            defaultValue={item.dataType}
            onSelectionChange={(selection) =>
              changeDataType(item.id, selection?.value as string)
            }
            error={
              validationRuleError && !item.dataType ? 'Select a data type' : ''
            }
          />
          <div className="dragabbleButtonWrapper">
            <Link
              to={''}
              style={{ display: 'flex', gap: '10px', alignItems: 'center' }}
              onClick={() => deleteItem(item.id)}
              className="link"
            >
              <MdDeleteOutline />
              {t('global.delete')}
            </Link>
            <FormCheckbox
              label=""
              item={{
                label: t('datasetGroups.createDataset.dataClass'),
                value: 'active',
              }}
              name="dataClass"
              checked={item.isDataClass}
              onChange={() => setIsDataClass(item.id, item.isDataClass)}
              style={{
                width: '150px',
              }}
            />
            <MdDehaze className="link" size={30} color="#7A7C8A" />
          </div>
        </div>
      </Card>
    </div>
  );
};

export default DraggableItem;
