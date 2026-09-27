import { useEffect } from 'react';

/**
 * Sets document.title to `title | VaniGuard` while the component is mounted,
 * and restores the default on unmount.
 */
export default function useDocTitle(title) {
  useEffect(() => {
    const prev = document.title;
    document.title = title ? `${title} | VaniGuard` : 'VaniGuard — AI Voice Cloning Defense';
    return () => {
      document.title = prev;
    };
  }, [title]);
}
