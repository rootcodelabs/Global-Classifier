import React, {
  createContext,
  FC,
  PropsWithChildren,
  ReactNode,
  useMemo,
  useState,
} from 'react';
import * as RadixDialog from '@radix-ui/react-dialog';
import { MdOutlineClose } from 'react-icons/md';
import clsx from 'clsx';
import '../components/Dialog/Dialog.scss';
import Icon from 'components/Icon';
import Track from 'components/Track';

type DialogProps = {
  title?: string | null;
  footer?: ReactNode;
  size?: 'default' | 'large';
  content: ReactNode;
};

type DialogContextType = {
  open: (dialog: DialogProps) => void;
  close: () => void;
};
// operates Dialog modals where dynamic contents not involved
export const DialogContext = createContext<DialogContextType>(null!);

export const DialogProvider: FC<PropsWithChildren<{}>> = ({ children }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [dialogProps, setDialogProps] = useState<DialogProps | null>(null);

  const open = (dialog: DialogProps) => {
    setDialogProps(dialog);
    setIsOpen(true);
  };

  const close = () => {
    setIsOpen(false);
    setDialogProps(null);
  };

  const contextValue = useMemo(() => ({ open, close }), []);

  return (
    <DialogContext.Provider value={contextValue}>
      {children}
      {dialogProps && (
        <RadixDialog.Root open={isOpen} onOpenChange={close}>
          <RadixDialog.Portal>
            <RadixDialog.Overlay className="dialog__overlay" />
            <RadixDialog.Content
              className={clsx(
                'dialog',
                `dialog--${dialogProps.size || 'default'}`
              )}
            >
              {dialogProps.title && (
                <div className="dialog__header">
                  <RadixDialog.Title className="h3 dialog__title">
                    {dialogProps.title}
                  </RadixDialog.Title>
                  <RadixDialog.Close asChild>
                    <button className="dialog__close">
                      <Icon icon={<MdOutlineClose />} size="medium" />
                    </button>
                  </RadixDialog.Close>
                </div>
              )}
              <div className="dialog__body">{dialogProps.content}</div>
              {dialogProps.footer && (
                <Track className="dialog__footer" gap={16} justify="end">
                  {dialogProps.footer}
                </Track>
              )}
            </RadixDialog.Content>
          </RadixDialog.Portal>
        </RadixDialog.Root>
      )}
    </DialogContext.Provider>
  );
};
