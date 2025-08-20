import { ButtonHTMLAttributes, FC, PropsWithChildren, useRef } from 'react';
import clsx from 'clsx';

import './Button.scss';

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  appearance?: 'primary' | 'secondary' | 'text' | 'icon' | 'error' | 'success';
  size?: 'm' | 's';
  disabledWithoutStyle?: boolean;
  showLoadingIcon?: boolean;
};

const Button: FC<PropsWithChildren<ButtonProps>> = ({
  appearance = 'primary',
  size = 'm',
  disabled,
  disabledWithoutStyle = false,
  children,
  showLoadingIcon = false,
  ...rest
}) => {
  const ref = useRef<HTMLButtonElement>(null);

  const buttonClasses = clsx(
    'btn',
    `btn--${appearance}`,
    `btn--${size}`,
    disabled && 'btn--disabled'
  );

  return (
    <button
      className={buttonClasses}
      ref={ref}
      disabled={disabled || disabledWithoutStyle}
      {...rest}
    >
      {children}
      {showLoadingIcon && (
        <div
          style={{
            height: '20px',
          }}
        >
          {' '}
          <div
            className="spinner"
            style={{ width: 20, height: 20, borderTop: ' 4px solid #FFFFFF' }}
          ></div>
        </div>
      )}
    </button>
  );
};

export default Button;