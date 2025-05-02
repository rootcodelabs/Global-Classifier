import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import FormInput from '../FormInput';
import Button from 'components/Button';
import Track from 'components/Track';
import { useTranslation } from 'react-i18next';

type DynamicFormProps = {
  formData: { [key: string]: string | number };
  onSubmit: (data: any) => void;
  setPatchUpdateModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
};

const DynamicForm: React.FC<DynamicFormProps> = ({
  formData,
  onSubmit,
  setPatchUpdateModalOpen,
}) => {
  const { register, handleSubmit, getValues, watch } = useForm({
    defaultValues: formData,
  });

  const [isChanged, setIsChanged] = useState(false);

  const allValues = watch();
  const { t } = useTranslation();

  const checkIfChanged = () => {
    const currentValues = getValues();
    const isDifferent = Object.keys(formData).some(
      (key) => currentValues[key] !== formData[key]
    );
    setIsChanged(isDifferent);
  };

  useEffect(() => {
    checkIfChanged();
  }, [allValues]);

  const renderInput = (key: string) => {
    const isRowID = key.toLowerCase() === 'rowid';
    const inputType = isRowID ? 'number' : 'text';

    return (
      <div style={{ display: isRowID ? 'none' : 'block' }}>
        <label>{key}</label>
        <FormInput
          label=""
          {...register(key)}
          type={inputType}
          placeholder={key}
          defaultValue={isRowID ? (formData[key] as number) : formData[key]}
        />
      </div>
    );
  };

  const handleFormSubmit = (data: any) => {
    onSubmit(data);
  };

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)}>
      {Object.keys(formData).map((key) => (
        <div key={key}>
          <div style={{ marginBottom: '15px' }}>{renderInput(key)}</div>
        </div>
      ))}
      <Track className="dialog__footer" gap={16} justify="end">
        <div className="flex-grid">
          <Button
            appearance="secondary"
            onClick={() => setPatchUpdateModalOpen(false)}
          >
            Cancel
          </Button>
          <Button type="submit" disabled={!isChanged}>
            {t('global.save')}
          </Button>
        </div>
      </Track>
    </form>
  );
};

export default DynamicForm;
