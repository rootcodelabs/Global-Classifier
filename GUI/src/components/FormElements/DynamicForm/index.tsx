import React, { useEffect, useState } from 'react';
import { useForm, Controller } from 'react-hook-form';
import FormInput from '../FormInput';
import FormSelect from '../FormSelect';
import Button from 'components/Button';
import Track from 'components/Track';
import { useTranslation } from 'react-i18next';
import { SelectedRowPayload } from 'types/datasets';

type ClientOption = { label: string; value: string; clientId: number | string };

type DynamicFormProps = {
  formData: {id:string |number, question: string; clientName: string; clientId?: number | string };
  clientOptions: ClientOption[];
  onSubmit: (data: SelectedRowPayload) => void;
  setPatchUpdateModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
};

const DynamicForm: React.FC<DynamicFormProps> = ({
  formData,
  clientOptions,
  onSubmit,
  setPatchUpdateModalOpen,
}) => {
  const { control, handleSubmit, watch, getValues } = useForm({
    defaultValues: formData,
  });
  const [isChanged, setIsChanged] = useState(false);
  const { t } = useTranslation();

  const allValues = watch();
const [selectedClientId, setSelectedClientId] = useState(formData.clientId ?? '');

  useEffect(() => {
    const currentValues = getValues();
    setIsChanged(
      currentValues.question !== formData.question ||
      currentValues.clientId !== formData.clientId
    );
  }, [allValues, formData, getValues]);

 const handleFormSubmit = (data: any) => {
  // Find the selected client option
  const selectedClient = clientOptions.find(opt => opt.value === data.clientId);
  onSubmit({
    id: formData.id, // Always return the id from formData
    question: data.question,
    clientId: selectedClient?.value ?? "0",
    clientName: selectedClient?.label ?? data.clientName,
  });
};

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)}>
      <div style={{ marginBottom: '15px' }}>
        <label>{t('datasets.detailedView.question')}</label>
        <Controller
          name="question"
          control={control}
          render={({ field }) => (
            <FormInput
              label=""
              {...field}
              type="text"
            />
          )}
        />
      </div>
      <div style={{ marginBottom: '15px' }}>
        <label>{t('datasets.detailedView.clientName')}</label>
        <Controller
          name="clientId"
          control={control}
          render={({ field }) => (
            <FormSelect
              label=""
              options={clientOptions.map(opt => ({
                label: opt.label,
                value: opt.value,
              }))}
              {...field}
              onSelectionChange={(selected) => { 
                              const value = typeof selected?.value === 'object'
                                ? (selected?.value.id ?? '')
                                : (selected?.value ?? '');
                              setSelectedClientId(value);               
                              field.onChange(value);
                            }}
              defaultValue={selectedClientId}
            />
          )}
        />
      </div>
      <Track className="dialog__footer" gap={16} justify="end">
        <div className="flex-grid">
          <Button
            appearance="secondary"
            onClick={() => setPatchUpdateModalOpen(false)}
          >
            {t('global.cancel')}
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