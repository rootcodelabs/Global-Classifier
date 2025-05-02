import React, { useRef, useState } from 'react';
import styles from "../../page.module.css";

const CopyableTextField: React.FC<{ value: string }> = ({ value }) => {
  const [copied, setCopied] = useState(false);
  const textFieldRef = useRef<HTMLInputElement>(null);

  const copyToClipboard = async () => {
    if (textFieldRef.current) {
      try {
        await navigator.clipboard.writeText(textFieldRef.current.value);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } catch (err) {
        console.error('Failed to copy text: ', err);
      }
    }
  };

  return (
    <div className={styles.copyableTextField}>
      <input
        type="text"
        ref={textFieldRef}
        value={value}
        readOnly
        style={{ marginRight: '10px' }}
      />
      <button className={styles.btn} onClick={copyToClipboard}>
        {copied ? 'Copied!' : 'Copy'}
      </button>
    </div>
  );
};

export default CopyableTextField;