import { DialogContext } from 'context/DialogContext';
import { useContext } from 'react';

export const useDialog = () => useContext(DialogContext);
