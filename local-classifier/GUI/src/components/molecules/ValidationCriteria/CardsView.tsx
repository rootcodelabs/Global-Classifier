import React, { FC, PropsWithChildren } from 'react';
import { DndProvider } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import Button from 'components/Button';
import { ValidationRule } from 'types/datasetGroups';
import { v4 as uuidv4 } from 'uuid';
import DraggableItem from './DraggableItem/DraggableItem';
import { useTranslation } from 'react-i18next';

type ValidationRulesProps = {
  validationRules?: ValidationRule[];
  setValidationRules: React.Dispatch<React.SetStateAction<ValidationRule[]>>;
  validationRuleError?: boolean;
  setValidationRuleError: React.Dispatch<React.SetStateAction<boolean>>;
};
const ValidationCriteriaCardsView: FC<
  PropsWithChildren<ValidationRulesProps>
> = ({
  validationRules,
  setValidationRules,
  setValidationRuleError,
  validationRuleError,
}) => {
  const { t } = useTranslation();
  const moveItem = (fromIndex: number, toIndex: number) => {
    const updatedItems = Array.from(validationRules ?? []);
    const [movedItem] = updatedItems.splice(fromIndex, 1);
    updatedItems.splice(toIndex, 0, movedItem);
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

  return (
    <DndProvider backend={HTML5Backend}>
      <div className="title-sm">
        {t('datasetGroups.createDataset.validationCriteria')}
      </div>
      {validationRules?.map((item, index) => (
        <DraggableItem
          key={item.id}
          index={index}
          item={item}
          moveItem={moveItem}
          validationRuleError={validationRuleError}
          setValidationRuleError={setValidationRuleError}
          setValidationRules={setValidationRules}
          validationRules={validationRules}
        />
      ))}
      <div className="flex justify-end">
        <Button onClick={addNewClass}>
          {t('datasetGroups.createDataset.addClassButton')}
        </Button>
      </div>
    </DndProvider>
  );
};

export default ValidationCriteriaCardsView;
