import React from 'react';
import * as Progress from '@radix-ui/react-progress';
import './index.scss';

type ProgressBarProps = {
  value: number;
  max: number;
  label?: string;
};

const ProgressBar: React.FC<ProgressBarProps> = ({ value, max, label }) => {
  return (
    <div className="progress-bar-container">
      <Progress.Root className="progress-bar-root" value={value} max={max}>
        <Progress.Indicator
          className="progress-bar-indicator"
          style={{ width: `${(value / max) * 100}%` }}
        />
      </Progress.Root>
      {label && <label className="progress-bar-label">{label}</label>}

    </div>
  );
};

export default ProgressBar;
