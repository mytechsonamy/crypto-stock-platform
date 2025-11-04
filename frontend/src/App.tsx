/**
 * Main App component
 */

import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Header, Sidebar, Main } from '@/components/Layout';
import { ChartContainer } from '@/components/Chart';
import { useMockData } from '@/hooks/useMockData';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30000, // 30 seconds
    },
  },
});

function App() {
  // Disable mock data - using real backend data
  useMockData(false);

  return (
    <QueryClientProvider client={queryClient}>
      <div className="flex flex-col h-screen">
        <Header />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar />
          <Main>
            <ChartContainer />
          </Main>
        </div>
      </div>
    </QueryClientProvider>
  );
}

export default App;
