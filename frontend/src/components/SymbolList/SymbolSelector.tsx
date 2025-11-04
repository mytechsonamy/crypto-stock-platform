/**
 * Symbol Selector Component
 * Fetches and displays available symbols grouped by exchange
 */

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useChartStore } from '@/store/chartStore';
import { apiService } from '@/services/api';

export const SymbolSelector: React.FC = () => {
  const { symbol: currentSymbol, setSymbol } = useChartStore();
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  // Fetch symbols from API
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['symbols'],
    queryFn: () => apiService.getSymbols(),
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 2,
  });

  // Filter symbols based on search term
  const filterSymbols = (symbols: string[]) => {
    if (!searchTerm) return symbols;
    return symbols.filter((s) =>
      s.toLowerCase().includes(searchTerm.toLowerCase())
    );
  };

  const handleSelect = (symbol: string) => {
    setSymbol(symbol);
    setIsOpen(false);
    setSearchTerm('');
  };

  return (
    <div className="relative">
      {/* Dropdown Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors"
      >
        <div className="flex items-center space-x-2">
          <svg
            className="w-5 h-5 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"
            />
          </svg>
          <span className="text-white font-medium">{currentSymbol}</span>
        </div>
        <svg
          className={`w-5 h-5 text-gray-400 transition-transform ${
            isOpen ? 'transform rotate-180' : ''
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-dark-800 rounded-lg shadow-xl border border-dark-700 z-50 max-h-96 overflow-hidden flex flex-col">
          {/* Search Input */}
          <div className="p-3 border-b border-dark-700">
            <input
              type="text"
              placeholder="Search symbols..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full px-3 py-2 bg-dark-900 border border-dark-600 rounded text-white placeholder-gray-500 focus:outline-none focus:border-primary-500"
              autoFocus
            />
          </div>

          {/* Loading State */}
          {isLoading && (
            <div className="p-8 text-center">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
              <p className="mt-2 text-gray-400">Loading symbols...</p>
            </div>
          )}

          {/* Error State */}
          {error && (
            <div className="p-8 text-center">
              <svg
                className="w-12 h-12 text-red-500 mx-auto mb-2"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <p className="text-red-400 mb-3">Failed to load symbols</p>
              <button
                onClick={() => refetch()}
                className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded transition-colors"
              >
                Retry
              </button>
            </div>
          )}

          {/* Symbols List */}
          {data && !isLoading && !error && (
            <div className="overflow-y-auto">
              {/* Binance Symbols */}
              {data.binance && data.binance.length > 0 && (
                <div>
                  <div className="px-4 py-2 bg-dark-900 text-xs font-semibold text-gray-400 sticky top-0">
                    Binance (Crypto)
                  </div>
                  {filterSymbols(data.binance).map((symbol) => (
                    <button
                      key={symbol}
                      onClick={() => handleSelect(symbol)}
                      className={`w-full text-left px-4 py-2 hover:bg-dark-700 transition-colors ${
                        currentSymbol === symbol ? 'bg-primary-600 text-white' : 'text-gray-300'
                      }`}
                    >
                      <div className="font-medium">{symbol}</div>
                    </button>
                  ))}
                </div>
              )}

              {/* Alpaca Symbols */}
              {data.alpaca && data.alpaca.length > 0 && (
                <div>
                  <div className="px-4 py-2 bg-dark-900 text-xs font-semibold text-gray-400 sticky top-0">
                    Alpaca (US Stocks)
                  </div>
                  {filterSymbols(data.alpaca).map((symbol) => (
                    <button
                      key={symbol}
                      onClick={() => handleSelect(symbol)}
                      className={`w-full text-left px-4 py-2 hover:bg-dark-700 transition-colors ${
                        currentSymbol === symbol ? 'bg-primary-600 text-white' : 'text-gray-300'
                      }`}
                    >
                      <div className="font-medium">{symbol}</div>
                    </button>
                  ))}
                </div>
              )}

              {/* Yahoo Symbols */}
              {data.yahoo && data.yahoo.length > 0 && (
                <div>
                  <div className="px-4 py-2 bg-dark-900 text-xs font-semibold text-gray-400 sticky top-0">
                    Yahoo Finance (Stocks)
                  </div>
                  {filterSymbols(data.yahoo).map((symbol) => (
                    <button
                      key={symbol}
                      onClick={() => handleSelect(symbol)}
                      className={`w-full text-left px-4 py-2 hover:bg-dark-700 transition-colors ${
                        currentSymbol === symbol ? 'bg-primary-600 text-white' : 'text-gray-300'
                      }`}
                    >
                      <div className="font-medium">{symbol}</div>
                    </button>
                  ))}
                </div>
              )}

              {/* No Results */}
              {searchTerm &&
                (!data.binance?.length && !data.alpaca?.length && !data.yahoo?.length) && (
                  <div className="p-8 text-center text-gray-500">
                    No symbols found matching "{searchTerm}"
                  </div>
                )}
            </div>
          )}
        </div>
      )}

      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  );
};
