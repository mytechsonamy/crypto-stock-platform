/**
 * Sidebar component with symbol selector and indicator panel
 */

import React from 'react';
import { SymbolSelector } from '@/components/SymbolList/SymbolSelector';
import { IndicatorPanel } from '@/components/Indicators/IndicatorPanel';

export const Sidebar: React.FC = () => {

  return (
    <aside className="w-64 bg-dark-900 border-r border-dark-700 overflow-y-auto">
      {/* Symbol Selector */}
      <div className="p-4 border-b border-dark-700">
        <h3 className="text-sm font-semibold text-gray-400 mb-3">Symbol</h3>
        <SymbolSelector />
      </div>

      {/* Indicator Panel */}
      <div className="p-4">
        <IndicatorPanel />
      </div>
    </aside>
  );
};
