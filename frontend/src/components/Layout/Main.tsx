/**
 * Main content area component
 */

import React from 'react';

interface MainProps {
  children: React.ReactNode;
}

export const Main: React.FC<MainProps> = ({ children }) => {
  return (
    <main className="flex-1 overflow-hidden bg-dark-950">
      {children}
    </main>
  );
};
