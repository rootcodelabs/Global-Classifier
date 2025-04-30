import React from 'react';
import './index.scss';
import { MdClose } from 'react-icons/md';

type LabelChipProps = {
  label: string;
  onRemove: () => void;
};

const LabelChip: React.FC<LabelChipProps> = ({ label, onRemove }) => {
  return (
    <div className="label-chip">
      <span className="label-chip__label">{label}</span>
      <button
        onClick={onRemove}
        className="label-chip__button"
        aria-label={`Remove ${label}`}
      >
        <MdClose />
      </button>
    </div>
  );
};

export default LabelChip;
