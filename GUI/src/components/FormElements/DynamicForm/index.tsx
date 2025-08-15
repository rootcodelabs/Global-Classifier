import React, { useEffect, useState } from 'react';
import { useForm, Controller } from 'react-hook-form';
import FormInput from '../FormInput';
import FormSelect from '../FormSelect';
import Button from 'components/Button';
import Track from 'components/Track';
import { useTranslation } from 'react-i18next';
import { SelectedRowPayload } from 'types/datasets';

type ClientOption = { label: string; value: string; agencyId: number | string };

type DynamicFormProps = {
  formData: {itemId:string |number, dataItem: string; agencyName: string; agencyId?: number | string };
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
const [selectedClientId, setSelectedClientId] = useState(formData.agencyId ?? '');

  useEffect(() => {
    const currentValues = getValues();
    setIsChanged(
      currentValues.dataItem !== formData.dataItem ||
      currentValues.agencyId !== formData.agencyId
    );
  }, [allValues, formData, getValues]);

 const handleFormSubmit = (data: any) => {
  const selectedClient = clientOptions.find(opt => opt.value === data.agencyId);
  onSubmit({
    itemId: formData.itemId, 
    dataItem: data.dataItem,
    agencyId: selectedClient?.value ?? "0",
    agencyName: selectedClient?.label ?? data.agencyName,
  });
};

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)}>
      <div style={{ marginBottom: '15px' }}>
        <label>{t('datasets.detailedView.data')}</label>
        <Controller
          name="dataItem"
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
          name="agencyId"
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