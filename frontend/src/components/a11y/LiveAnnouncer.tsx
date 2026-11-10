import React, { createContext, useContext, useState, useCallback, useRef } from 'react';

interface AnnouncerContextType {
  announce: (message: string, mode?: 'polite' | 'assertive') => void;
}

const AnnouncerContext = createContext<AnnouncerContextType>({
  announce: () => {},
});

export const useAnnounce = () => useContext(AnnouncerContext);

export const LiveAnnouncerProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [politeMessage, setPoliteMessage] = useState('');
  const [assertiveMessage, setAssertiveMessage] = useState('');
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const announce = useCallback((message: string, mode: 'polite' | 'assertive' = 'polite') => {
    if (!message) return;

    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    if (mode === 'assertive') {
      setAssertiveMessage('');
      // Small timeout ensures screen readers detect DOM mutation
      setTimeout(() => setAssertiveMessage(message), 50);
    } else {
      setPoliteMessage('');
      setTimeout(() => setPoliteMessage(message), 50);
    }

    // Clear after 7 seconds so repeat announcements trigger fresh mutations
    timeoutRef.current = setTimeout(() => {
      setPoliteMessage('');
      setAssertiveMessage('');
    }, 7000);
  }, []);

  return (
    <AnnouncerContext.Provider value={{ announce }}>
      {children}

      {/* Screen Reader Off-screen Live Regions */}
      <div
        id="a11y-live-polite"
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {politeMessage}
      </div>

      <div
        id="a11y-live-assertive"
        role="alert"
        aria-live="assertive"
        aria-atomic="true"
        className="sr-only"
      >
        {assertiveMessage}
      </div>
    </AnnouncerContext.Provider>
  );
};
