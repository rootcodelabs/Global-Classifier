import { FC, useId } from 'react';
import './FormRadios.scss';

type FormRadiosType = {
  label: string;
  name: string;
  hideLabel?: boolean;
  items: {
    label: string;
    value: string;
  }[] |undefined;
  onChange: (selectedValue: string) => void;
  selectedValue?: string;
  isStack?: boolean;
  error?: string;
};

const FormRadios: FC<FormRadiosType> = ({
  label,
  name,
  hideLabel,
  items,
  onChange,
  selectedValue,
  isStack = false,
  error,
}) => {
  const id = useId();

  return (
    <div>
      <div>
        <fieldset className="radios" role="group">
          {label && !hideLabel && (
            <label className="radios__label">{label}</label>
          )}
          <div className={isStack ? 'radios__stack' : 'radios__wrapper'}>
            {items?.map((item, index) => (
              <div key={`${item.value}-${index}`} className="radios__item">
                <input
                  type="radio"
                  name={name}
                  id={`${id}-${item.value}`}
                  value={item.value}
                  checked={selectedValue === item.value}
                  onChange={(event) => {
                    onChange(event.target.value);
                  }}
                />
                <label htmlFor={`${id}-${item.value}`}>{item.label}</label>
              </div>
            ))}
          </div>
        </fieldset>
      </div>
      <div>{error && <p className="input__inline_error">{error}</p>}</div>
    </div>
  );
};

export default FormRadios;




