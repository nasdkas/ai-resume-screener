import { useEffect, useRef } from 'react';

export function usePolling(callback: () => void, enabled: boolean, intervalMs: number = 3000) {
  const savedCallback = useRef(callback);

  useEffect(() => {
    savedCallback.current = callback;
  });

  useEffect(() => {
    if (!enabled) return;
    const id = setInterval(() => savedCallback.current(), intervalMs);
    return () => clearInterval(id);
  }, [enabled, intervalMs]);
}
