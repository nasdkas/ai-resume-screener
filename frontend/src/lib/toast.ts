import { useAppStore } from '../store';
import type { Toast } from '../components/Toast';

const toastFn = (message: string, type: Toast['type'] = 'info', duration?: number) => {
  useAppStore.getState().addToast({ message, type, duration });
};

export const toast = Object.assign(toastFn, {
  success: (msg: string, duration?: number) => toastFn(msg, 'success', duration),
  error: (msg: string, duration?: number) => toastFn(msg, 'error', duration),
  warning: (msg: string, duration?: number) => toastFn(msg, 'warning', duration),
  info: (msg: string, duration?: number) => toastFn(msg, 'info', duration),
});
