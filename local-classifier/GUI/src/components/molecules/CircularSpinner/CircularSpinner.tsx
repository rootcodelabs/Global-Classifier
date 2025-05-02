import React from 'react';
import './Spinner.scss';

interface SpinnerProps {
  size?: number;
}

const CircularSpinner: React.FC<SpinnerProps> = ({ size = 80 }) => {
  return (
    <div className="spinner-container">
      <div
        className="spinner"
        style={{ width: size, height: size, borderWidth: size / 10 }}
      ></div>
    </div>
  );
};

export default CircularSpinner;