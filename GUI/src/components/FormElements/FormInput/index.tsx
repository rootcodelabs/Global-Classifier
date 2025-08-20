import { forwardRef, InputHTMLAttributes, PropsWithChildren, useId } from 'react';
import clsx from 'clsx';
import './FormInput.scss';
import { DefaultTFuncReturn } from 'i18next';

type InputProps = PropsWithChildren<InputHTMLAttributes<HTMLInputElement>> & {
  label: string;
  name: string;
  hideLabel?: boolean;
  maxLength?: number;
  error?: string;
  placeholder?:string | DefaultTFuncReturn;
};

const FormInput = forwardRef<HTMLInputElement, InputProps>(
  (
    { label, name, disabled, hideLabel, maxLength, error, children,placeholder, ...rest },
    ref
  ) => {
    const id = useId();

    const inputClasses = clsx('input', disabled && 'input--disabled', error && 'input--error');

    return (
      <div className={inputClasses}>
        {label && !hideLabel && (
          <label htmlFor={id} className="input__label">
            {label}
          </label>
        )}
        <div className="input__wrapper">
          <input
            className={inputClasses}
            name={name}
            maxLength={maxLength}
            id={id}
            ref={ref}
            aria-label={hideLabel ? label : undefined}
            {...rest}
            placeholder={placeholder}
          />
          {error && <p className="input__inline_error">{error}</p>}
          {children}
        </div>
      </div>
    );
  }
);

export default FormInput;
