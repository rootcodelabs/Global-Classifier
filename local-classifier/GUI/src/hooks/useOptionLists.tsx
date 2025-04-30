import { useTranslation } from 'react-i18next';

// maps translations with dropdown options
const useOptionLists = () => {
  const { t } = useTranslation();

  const dataTypesConfigs = [
    { label: t('optionLists.text'), value: 'text' },
    { label: t('optionLists.numbers'), value: 'numbers' },
    { label: t('optionLists.dateTimes'), value: 'datetime' },
    { label: t('optionLists.email'), value: 'email' },
    { label: t('optionLists.fileAttachements'), value: 'file_attachments' },
  ];

  const importOptionsConfigs = [
    { label: t('optionLists.importToAdd'), value: 'add' },
    { label: t('optionLists.importToDelete'), value: 'delete' },
  ];

  return {
    dataTypesConfigs,
    importOptionsConfigs,
  };
};

export default useOptionLists;
