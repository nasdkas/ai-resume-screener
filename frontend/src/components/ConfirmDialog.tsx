import { useEffect, useRef } from 'react';
import { useAppStore } from '../store';
import { AlertTriangle, X } from 'lucide-react';

export interface ConfirmDialogState {
  open: boolean;
  message: string;
  title?: string;
  confirmText?: string;
  cancelText?: string;
  variant?: 'danger' | 'warning' | 'info';
  resolve?: (value: boolean) => void;
}

export function ConfirmDialogProvider() {
  const confirmDialog = useAppStore((s) => s.confirmDialog);
  const setConfirmDialog = useAppStore((s) => s.setConfirmDialog);
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (confirmDialog.open) {
      confirmRef.current?.focus();
    }
  }, [confirmDialog.open]);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && confirmDialog.open) {
        confirmDialog.resolve?.(false);
        setConfirmDialog({ open: false, message: '' });
      }
    };
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, [confirmDialog.open, confirmDialog.resolve, setConfirmDialog]);

  if (!confirmDialog.open) return null;

  const handleConfirm = () => {
    confirmDialog.resolve?.(true);
    setConfirmDialog({ open: false, message: '' });
  };

  const handleCancel = () => {
    confirmDialog.resolve?.(false);
    setConfirmDialog({ open: false, message: '' });
  };

  const variantStyles = {
    danger: 'bg-red-600 hover:bg-red-700',
    warning: 'bg-amber-600 hover:bg-amber-700',
    info: 'bg-secondary hover:bg-blue-600',
  };

  const variant = confirmDialog.variant || 'danger';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/50" onClick={handleCancel} />
      <div className="relative bg-white rounded-xl shadow-2xl max-w-md w-full mx-4 p-6" role="dialog">
        <button
          onClick={handleCancel}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
        >
          <X className="h-5 w-5" />
        </button>
        <div className="flex items-start space-x-4">
          <div className="flex-shrink-0 w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
            <AlertTriangle className="h-5 w-5 text-red-600" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-gray-900">
              {confirmDialog.title || '确认操作'}
            </h3>
            <p className="mt-2 text-sm text-gray-600 leading-relaxed">
              {confirmDialog.message}
            </p>
          </div>
        </div>
        <div className="mt-6 flex items-center justify-end space-x-3">
          <button
            onClick={handleCancel}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            {confirmDialog.cancelText || '取消'}
          </button>
          <button
            ref={confirmRef}
            onClick={handleConfirm}
            className={`px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors ${variantStyles[variant]}`}
          >
            {confirmDialog.confirmText || '确定'}
          </button>
        </div>
      </div>
    </div>
  );
}

export function confirmAsync(message: string, options?: {
  title?: string;
  confirmText?: string;
  cancelText?: string;
  variant?: 'danger' | 'warning' | 'info';
}): Promise<boolean> {
  return new Promise((resolve) => {
    useAppStore.getState().setConfirmDialog({
      open: true,
      message,
      title: options?.title,
      confirmText: options?.confirmText,
      cancelText: options?.cancelText,
      variant: options?.variant,
      resolve,
    });
  });
}
