import { FC, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, Card, Dialog, FormInput, FormRadios } from 'components';
import LabelChip from 'components/LabelChip';
import FileUpload, { FileUploadHandle } from 'components/FileUpload';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  addStopWord,
  deleteStopWord,
  deleteStopWords,
  getStopWords,
  importStopWords,
} from 'services/datasets';
import { stopWordsQueryKeys } from 'utils/queryKeys';
import { ButtonAppearanceTypes } from 'enums/commonEnums';
import { StopWordImportOptions } from 'enums/datasetEnums';
import { useDialog } from 'hooks/useDialog';
import { StopWordsImportResponse } from 'types/datasetGroups';
import useOptionLists from 'hooks/useOptionLists';
import './StopWords.scss';

const StopWords: FC = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const { open } = useDialog();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [importOption, setImportOption] = useState('');
  const [file, setFile] = useState<File | null>();
  const fileUploadRef = useRef<FileUploadHandle>(null);
  const { importOptionsConfigs } = useOptionLists();
  const { register, setValue, watch } = useForm({
    defaultValues: {
      stopWord: '',
    },
  });

  const { data: stopWordsData, refetch: stopWordRefetch } = useQuery(
    stopWordsQueryKeys.GET_ALL_STOP_WORDS(),
    () => getStopWords()
  );

  const watchedStopWord = watch('stopWord');

  const removeStopWord = (wordToRemove: string) => {
    deleteStopWordMutation.mutate({ stopWords: [wordToRemove] });
  };

  const addStopWordMutation = useMutation({
    mutationFn: (data: { stopWords: string[] }) => addStopWord(data),
    onSuccess: async () => {
      await queryClient.invalidateQueries(
        stopWordsQueryKeys.GET_ALL_STOP_WORDS()
      );
    },
    onError: () => {},
  });

  const deleteStopWordMutation = useMutation({
    mutationFn: (data: { stopWords: string[] }) => deleteStopWord(data),
    onSuccess: async () => {
      await queryClient.invalidateQueries(
        stopWordsQueryKeys.GET_ALL_STOP_WORDS()
      );
    },
    onError: () => {},
  });

  const importMutationSuccessFunc = async (
    response: StopWordsImportResponse
  ) => {
    setIsModalOpen(false);
    if (response.response?.operationSuccessful) {
      open({
        title: t('stopWords.importModal.successTitle') ?? '',
        content: <p>{t('stopWords.importModal.successDesc') ?? ''}</p>,
      });
      setFile(null);
      await queryClient.invalidateQueries(
        stopWordsQueryKeys.GET_ALL_STOP_WORDS()
      );

      if (importOption === StopWordImportOptions.DELETE) {
        stopWordRefetch();
      }
    } else {
      open({
        title: t('stopWords.importModal.unsuccessTitle') ?? '',
        content: <p>{t('stopWords.importModal.unsuccessDesc') ?? ''}</p>,
      });
    }
    setImportOption('');
  };

  const importStopWordsMutation = useMutation({
    mutationFn: (file: File) => importStopWords(file),
    onSuccess: async (response) => {
      importMutationSuccessFunc(response);
    },
    onError: async () => {
      setIsModalOpen(true);
      open({
        title: t('stopWords.importModal.unsuccessTitle') ?? '',
        content: <p>{t('stopWords.importModal.unsuccessDesc') ?? ''}</p>,
      });
    },
  });

  const deleteStopWordsMutation = useMutation({
    mutationFn: (file: File) => deleteStopWords(file),
    onSuccess: async (response) => {
      importMutationSuccessFunc(response);
    },
    onError: async () => {
      setIsModalOpen(true);
      open({
        title: t('stopWords.importModal.unsuccessTitle') ?? '',
        content: <p>{t('stopWords.importModal.unsuccessDesc') ?? ''}</p>,
      });
    },
  });

  const handleFileSelect = (file: File | undefined) => {
    setFile(file);
  };

  const handleStopWordFileOperations = () => {
    if (
      importOption === StopWordImportOptions.ADD &&
      file &&
      file !== undefined
    ) {
      importStopWordsMutation.mutate(file);
    } else if (
      importOption === StopWordImportOptions.DELETE &&
      file &&
      file !== undefined
    )
      deleteStopWordsMutation.mutate(file);

    setIsModalOpen(false);
    open({
      title: t('stopWords.importModal.inprogressTitle') ?? '',
      content: <p>{t('stopWords.importModal.inprogressDesc') ?? ''}</p>,
    });
  };

  return (
    <div>
      <div className="container">
        <div className="title_container">
          <div className="title">{t('stopWords.title') ?? ''}</div>
          <Button onClick={() => setIsModalOpen(true)}>
            {t('stopWords.import') ?? ''}
          </Button>
        </div>
        <Card>
          {stopWordsData?.map((word: string) => (
            <LabelChip
              key={word}
              label={word}
              onRemove={() => removeStopWord(word)}
            />
          ))}
          <div className="flex-grid m-15">
            <FormInput
              {...register('stopWord')}
              value={watchedStopWord}
              name="stopWord"
              label=""
              placeholder={t('stopWords.stopWordInputHint') ?? ''}
            />
            <Button
              disabled={watchedStopWord === '' || !watchedStopWord.trim()}
              onClick={() => {
                setValue('stopWord', '');
                addStopWordMutation.mutate({
                  stopWords: [watchedStopWord.trim()],
                });
              }}
            >
              {t('stopWords.add') ?? ''}
            </Button>
          </div>
        </Card>
        {isModalOpen && (
          <Dialog
            isOpen={isModalOpen}
            onClose={() => {
              setIsModalOpen(false);
              setImportOption('');
            }}
            title={t('stopWords.importModal.title') ?? ''}
            footer={
              <div className="flex-grid">
                <Button
                  appearance={ButtonAppearanceTypes.SECONDARY}
                  onClick={() => {
                    setIsModalOpen(false);
                    setImportOption('');
                  }}
                >
                  {t('global.cancel') ?? ''}
                </Button>
                <Button
                  onClick={handleStopWordFileOperations}
                  disabled={
                    importOption === '' ||
                    file === null ||
                    file === undefined ||
                    importStopWordsMutation.isLoading ||
                    deleteStopWordMutation.isLoading
                  }
                  showLoadingIcon={importStopWordsMutation.isLoading}
                >
                  {t('stopWords.importModal.importButton') ?? ''}
                </Button>
              </div>
            }
          >
            <div>
              <p>{t('stopWords.importModal.selectionLabel') ?? ''}</p>
              <FormRadios
                isStack={true}
                name="importOption"
                label=""
                onChange={setImportOption}
                items={importOptionsConfigs}
                selectedValue={importOption}
              />
              <div className='m-20-0'>
              <p>{t('stopWords.importModal.attachements') ?? ''}</p>
              <FileUpload
                ref={fileUploadRef}
                disabled={importOption === ''}
                onFileSelect={handleFileSelect}
                accept={['xlsx', 'json', 'yaml', 'txt','yml']}
              />
              </div>
            </div>
          </Dialog>
        )}
      </div>
    </div>
  );
};

export default StopWords;
