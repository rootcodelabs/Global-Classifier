'use client';

import React from 'react';
import styles from "../../page.module.css";

const LoginButton = () => {
  const handleLogin = () => {
    window.location.href = '/api/auth';
  };

  return (
    <button className={styles.btn} onClick={handleLogin}>
      Login with Outlook
    </button>
  );
};

export default LoginButton;
