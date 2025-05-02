import { FormInput } from 'components/FormElements';
import React, {
  ChangeEvent,
  forwardRef,
  useImperativeHandle,
  Ref,
  useRef,
  useState,
} from 'react';
import { useTranslation } from 'react-i18next';

type FileUploadProps = {
  onFileSelect: (file: File | undefined) => void;
  accept?: string | string[];
  disabled?: boolean;
};

export type FileUploadHandle = {
  clearFile: () => void;
};

const FileUpload = forwardRef(
  (props: FileUploadProps, ref: Ref<FileUploadHandle>) => {
    const { onFileSelect, accept, disabled } = props;
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [errorMessage, setErrorMessage] = useState<string>('');
    const { t } = useTranslation();
    useImperativeHandle(ref, () => ({
      clearFile() {
        onFileSelect(undefined);
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
      },
    }));

    const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files ? e.target.files[0] : undefined;
      const maxFileSize = 20 * 1024 * 1024; // 20 MB in bytes

      if (file) {
        if (file.size > maxFileSize) {
          setErrorMessage(t('global.maxFileSize') ?? '');
          onFileSelect(undefined);
          if (fileInputRef.current) {
            fileInputRef.current.value = '';
          }
        } else {
          setErrorMessage('');
          onFileSelect(file);
        }
      } else {
        setErrorMessage('');
        onFileSelect(undefined);
      }
    };

    const restrictFormat = (accept: string | string[]) => {
      if (typeof accept === 'string') {
        if (accept === 'json') return '.json';
        else if (accept === 'xlsx') return '.xlsx';
        else if (accept === 'yaml') return '.yaml, .yml';
        return '';
      } else {
        return accept.map((ext) => `.${ext}`).join(', ');
      }
    };

    return (
      <div className="file-upload">
        <FormInput label="" name="" style={{ display: 'none' }}>
          <input
            type="file"
            onChange={handleFileChange}
            accept={restrictFormat(accept ?? '')}
            disabled={disabled}
            ref={fileInputRef}
          />
        </FormInput>
        {errorMessage && <p className="input__inline_error">{errorMessage}</p>}
        <button
          type="button"
          onClick={() => {
            onFileSelect(undefined);
            if (fileInputRef.current) {
              fileInputRef.current.value = '';
            }
            setErrorMessage('');
          }}
        >
          Clear
        </button>
      </div>
    );
  }
);

export default FileUpload;
