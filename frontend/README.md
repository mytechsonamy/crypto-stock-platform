# Crypto-Stock Platform Frontend

React + TypeScript + Vite frontend for the Crypto-Stock Platform.

## Features

- **Real-time Charts**: Lightweight Charts integration with WebSocket updates
- **Multiple Exchanges**: Support for Binance (crypto), Alpaca (US stocks), Yahoo Finance (BIST stocks)
- **Technical Indicators**: RSI, MACD, Bollinger Bands, SMA, EMA, and more
- **Dark Theme**: Modern dark UI with TailwindCSS
- **State Management**: Zustand with localStorage persistence
- **Type Safety**: Full TypeScript support with strict mode

## Tech Stack

- **React 18**: UI framework
- **TypeScript**: Type safety
- **Vite**: Build tool and dev server
- **TailwindCSS**: Styling
- **Lightweight Charts**: High-performance charting
- **Zustand**: State management
- **TanStack Query**: Data fetching and caching
- **Axios**: HTTP client

## Getting Started

### Prerequisites

- Node.js 18+ and npm/yarn/pnpm

### Installation

```bash
# Install dependencies
npm install

# Copy environment variables
cp .env.example .env

# Start development server
npm run dev
```

The app will be available at `http://localhost:3000`

### Build for Production

```bash
# Build
npm run build

# Preview production build
npm run preview
```

## Project Structure

```
frontend/
├── src/
│   ├── components/       # React components
│   │   ├── Layout/      # Layout components (Header, Sidebar, Main)
│   │   └── Chart/       # Chart components (coming soon)
│   ├── hooks/           # Custom React hooks
│   ├── services/        # API and WebSocket services
│   ├── store/           # Zustand stores
│   ├── types/           # TypeScript type definitions
│   ├── App.tsx          # Main App component
│   ├── main.tsx         # Entry point
│   └── index.css        # Global styles
├── public/              # Static assets
├── index.html           # HTML template
├── vite.config.ts       # Vite configuration
├── tailwind.config.js   # TailwindCSS configuration
├── tsconfig.json        # TypeScript configuration
└── package.json         # Dependencies and scripts
```

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
```

### Vite Configuration

The Vite config includes:
- Path aliases (`@/` → `src/`)
- API proxy for development
- WebSocket proxy
- Code splitting for vendors

## State Management

### Chart Store (Zustand)

The chart store manages:
- Selected symbol and timeframe
- Indicator toggles
- Chart data (bars and indicators)
- Connection status
- Loading and error states

Settings are persisted to localStorage.

```typescript
import { useChartStore } from '@/store/chartStore';

function MyComponent() {
  const { symbol, setSymbol, indicators, toggleIndicator } = useChartStore();
  // ...
}
```

## Type Definitions

All types are defined in `src/types/chart.types.ts`:

- `Candle`: OHLC bar data
- `Indicators`: Technical indicator values
- `ChartData`: Complete chart data
- `WSMessage`: WebSocket message types
- `SymbolInfo`: Symbol metadata

## Development

### Code Style

- ESLint for linting
- TypeScript strict mode
- Prettier for formatting (recommended)

### Hot Module Replacement

Vite provides instant HMR for fast development.

### Type Checking

```bash
# Run TypeScript compiler
npm run build
```

## Deployment

### Docker

The frontend is containerized and included in the main docker-compose:

```bash
docker-compose up frontend
```

### Static Hosting

Build and deploy the `dist/` folder to any static hosting service:

- Vercel
- Netlify
- AWS S3 + CloudFront
- GitHub Pages

## Performance

- Code splitting for vendor libraries
- Lazy loading for routes (if implemented)
- Memoization with React.memo
- Optimized chart updates (throttling and batching)
- Service worker for caching (optional)

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

## Troubleshooting

### Port Already in Use

Change the port in `vite.config.ts`:

```typescript
server: {
  port: 3001, // Change this
}
```

### WebSocket Connection Failed

Check that the backend is running and the WebSocket URL is correct in `.env`.

### Chart Not Rendering

Ensure Lightweight Charts is properly installed:

```bash
npm install lightweight-charts
```

## Next Steps

- [ ] Implement CandlestickChart component (Task 23)
- [ ] Add WebSocket integration (Task 24)
- [ ] Implement indicator panels
- [ ] Add chart controls
- [ ] Optimize performance

## Resources

- [React Documentation](https://react.dev/)
- [Vite Documentation](https://vitejs.dev/)
- [TailwindCSS Documentation](https://tailwindcss.com/)
- [Lightweight Charts Documentation](https://tradingview.github.io/lightweight-charts/)
- [Zustand Documentation](https://docs.pmnd.rs/zustand/)
- [TanStack Query Documentation](https://tanstack.com/query/)
