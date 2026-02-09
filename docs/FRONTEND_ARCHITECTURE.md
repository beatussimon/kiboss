# Frontend Architecture for KIBOSS

This document describes the React frontend architecture for KIBOSS.

---

## 1. Technology Stack

### 1.1 Core Technologies

| Layer | Technology | Version |
|-------|------------|---------|
| Framework | React | 18.x |
| Language | TypeScript | 5.x |
| State Management | Redux Toolkit | 2.x |
| Styling | TailwindCSS | 3.x |
| HTTP Client | Axios | 1.x |
| Routing | React Router | 6.x |
| Forms | React Hook Form | 7.x |
| Validation | Zod | 3.x |
| Date Handling | date-fns | 3.x |
| Icons | Lucide React | 0.x |

### 1.2 Additional Libraries

| Purpose | Library |
|---------|---------|
| WebSocket | @stomp/stompjs |
| Charts | recharts |
| Maps | react-leaflet |
| Calendar | react-big-calendar |
| Drag & Drop | @dnd-kit/core |
| Infinite Scroll | react-infinite-scroll-component |
| Toast Notifications | react-hot-toast |
| Loading Skeletons | react-loading-skeleton |

---

## 2. Project Structure

```
frontend/
├── public/
│   ├── index.html
│   ├── manifest.json
│   └── robots.txt
├── src/
│   ├── app/
│   │   ├── store.ts              # Redux store configuration
│   │   ├── hooks.ts              # Typed Redux hooks
│   │   └── slices/               # Redux slices
│   ├── assets/
│   ├── components/
│   │   ├── common/               # Shared components
│   │   ├── layout/               # Layout components
│   │   ├── forms/                # Form components
│   │   └── modals/               # Modal components
│   ├── features/                 # Feature-based modules
│   │   ├── auth/
│   │   ├── assets/
│   │   ├── bookings/
│   │   ├── rides/
│   │   ├── payments/
│   │   ├── messaging/
│   │   ├── notifications/
│   │   ├── ratings/
│   │   └── admin/
│   ├── hooks/                    # Custom React hooks
│   ├── services/                 # API services
│   ├── utils/                    # Utility functions
│   ├── types/                    # TypeScript types
│   ├── locales/                  # i18n translations
│   └── styles/                   # Global styles
├── tests/
├── .env
├── package.json
├── tsconfig.json
├── tailwind.config.js
└── vite.config.ts
```

---

## 3. Feature Architecture

### 3.1 Feature Module Structure

Each feature follows this structure:

```
features/
└── feature-name/
    ├── components/              # Feature-specific components
    │   ├── FeatureComponent.tsx
    │   └── SubComponent.tsx
    ├── hooks/                   # Feature-specific hooks
    │   ├── useFeature.ts
    │   └── useFeatureData.ts
    ├── services/                # Feature API services
    │   ├── api.ts
    │   └── endpoints.ts
    ├── types/                  # Feature types
    │   └── index.ts
    ├── utils/                   # Feature utilities
    │   └── helpers.ts
    ├── selectors.ts             # Redux selectors
    ├── slice.ts                 # Redux slice
    └── index.ts                 # Exports
```

### 3.2 Redux Slice Example

```typescript
// features/bookings/slice.ts

import { createSlice, PayloadAction, createAsyncThunk } from '@reduxjs/toolkit';
import { bookingApi } from './services/api';

// Types
interface Booking {
  id: string;
  status: BookingStatus;
  asset: Asset;
  startTime: string;
  endTime: string;
  totalPrice: number;
}

interface BookingState {
  bookings: Booking[];
  currentBooking: Booking | null;
  loading: boolean;
  error: string | null;
}

// Initial State
const initialState: BookingState = {
  bookings: [],
  currentBooking: null,
  loading: false,
  error: null,
};

// Async Thunks
export const fetchBookings = createAsyncThunk(
  'bookings/fetchAll',
  async (params: BookingFilters, { rejectWithValue }) => {
    try {
      const response = await bookingApi.getBookings(params);
      return response.data;
    } catch (error) {
      return rejectWithValue(error.message);
    }
  }
);

export const createBooking = createAsyncThunk(
  'bookings/create',
  async (bookingData: CreateBookingPayload, { rejectWithValue }) => {
    try {
      const response = await bookingApi.createBooking(bookingData);
      return response.data;
    } catch (error) {
      return rejectWithValue(error.message);
    }
  }
);

// Slice
const bookingSlice = createSlice({
  name: 'bookings',
  initialState,
  reducers: {
    setCurrentBooking: (state, action: PayloadAction<Booking | null>) => {
      state.currentBooking = action.payload;
    },
    clearError: (state) => {
      state.error = null;
    },
    updateBookingStatus: (state, action: PayloadAction<{id: string, status: string}>) => {
      const booking = state.bookings.find(b => b.id === action.payload.id);
      if (booking) {
        booking.status = action.payload.status as BookingStatus;
      }
    },
  },
  extraReducers: (builder) => {
    // Fetch bookings
    builder.addCase(fetchBookings.pending, (state) => {
      state.loading = true;
      state.error = null;
    });
    builder.addCase(fetchBookings.fulfilled, (state, action) => {
      state.loading = false;
      state.bookings = action.payload;
    });
    builder.addCase(fetchBookings.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload as string;
    });
    // Create booking
    builder.addCase(createBooking.fulfilled, (state, action) => {
      state.bookings.unshift(action.payload);
    });
  },
});

export const { setCurrentBooking, clearError, updateBookingStatus } = bookingSlice.actions;
export default bookingSlice.reducer;
```

### 3.3 Custom Hooks

```typescript
// hooks/useBooking.ts

import { useCallback } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { RootState } from '../app/store';
import { fetchBookings, createBooking } from '../features/bookings/slice';
import { useToast } from './useToast';

export function useBooking() {
  const dispatch = useDispatch();
  const toast = useToast();
  
  const { bookings, currentBooking, loading, error } = useSelector(
    (state: RootState) => state.bookings
  );
  
  const loadBookings = useCallback((filters?: BookingFilters) => {
    dispatch(fetchBookings(filters) as any);
  }, [dispatch]);
  
  const bookAsset = useCallback(async (data: CreateBookingPayload) => {
    try {
      const result = await dispatch(createBooking(data) as any);
      if (createBooking.fulfilled.match(result)) {
        toast.success('Booking created successfully!');
        return result.payload;
      }
      return null;
    } catch (err) {
      toast.error('Failed to create booking');
      return null;
    }
  }, [dispatch, toast]);
  
  return {
    bookings,
    currentBooking,
    loading,
    error,
    loadBookings,
    bookAsset,
  };
}
```

---

## 4. Component Architecture

### 4.1 Component Hierarchy

```
Layout
├── Header
│   ├── Logo
│   ├── Navigation
│   ├── SearchBar
│   ├── NotificationsDropdown
│   └── UserMenu
├── Sidebar (collapsible)
│   ├── NavLinks
│   └── QuickActions
├── MainContent
│   └── PageContent
└── Footer

Page
├── PageHeader
├── PageContent
│   ├── FeatureComponents
│   └── SharedComponents
└── PageFooter (actions)
```

### 4.2 Component Patterns

```typescript
// components/common/Card.tsx

interface CardProps {
  title?: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  onClick?: () => void;
}

export function Card({ title, children, actions, className = '', onClick }: CardProps) {
  return (
    <div 
      className={`bg-white rounded-lg shadow-sm border border-gray-200 ${onClick ? 'cursor-pointer hover:shadow-md transition-shadow' : ''}`}
      onClick={onClick}
    >
      {title && (
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
          {actions && <div className="flex gap-2">{actions}</div>}
        </div>
      )}
      <div className="p-6">{children}</div>
    </div>
  );
}
```

### 4.3 Form Components

```typescript
// components/forms/Input.tsx

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export function Input({ 
  label, 
  error, 
  helperText, 
  leftIcon, 
  rightIcon,
  className = '',
  ...props 
}: InputProps) {
  return (
    <div className="space-y-1">
      {label && (
        <label className="block text-sm font-medium text-gray-700">
          {label}
        </label>
      )}
      <div className="relative">
        {leftIcon && (
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
            {leftIcon}
          </div>
        )}
        <input
          className={`
            block w-full rounded-md border-gray-300 shadow-sm
            focus:border-indigo-500 focus:ring-indigo-500
            ${leftIcon ? 'pl-10' : 'pl-3'}
            ${rightIcon ? 'pr-10' : 'pr-3'}
            ${error ? 'border-red-500 focus:border-red-500 focus:ring-red-500' : ''}
            ${className}
          `}
          {...props}
        />
        {rightIcon && (
          <div className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400">
            {rightIcon}
          </div>
        )}
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {helperText && !error && <p className="text-sm text-gray-500">{helperText}</p>}
    </div>
  );
}
```

---

## 5. API Integration

### 5.1 Axios Configuration

```typescript
// services/api.ts

import axios from 'axios';
import { toast } from 'react-hot-toast';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('accessToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // Handle 401 - Token expired
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      try {
        const refreshToken = localStorage.getItem('refreshToken');
        const response = await axios.post('/api/v1/auth/refresh/', {
          refresh: refreshToken,
        });
        
        const { access } = response.data;
        localStorage.setItem('accessToken', access);
        originalRequest.headers.Authorization = `Bearer ${access}`;
        
        return api(originalRequest);
      } catch (refreshError) {
        // Redirect to login
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }
    
    // Show error toast
    const message = error.response?.data?.message || 'An error occurred';
    toast.error(message);
    
    return Promise.reject(error);
  }
);

export default api;
```

### 5.2 API Service Pattern

```typescript
// services/bookings.ts

import api from './api';
import { AxiosResponse } from 'axios';

export const bookingApi = {
  getBookings: (params?: BookingFilters): Promise<AxiosResponse<PaginatedResponse<Booking>>> => {
    return api.get('/bookings/', { params });
  },
  
  getBooking: (id: string): Promise<AxiosResponse<Booking>> => {
    return api.get(`/bookings/${id}/`);
  },
  
  createBooking: (data: CreateBookingPayload): Promise<AxiosResponse<Booking>> => {
    return api.post('/bookings/', data);
  },
  
  confirmPayment: (bookingId: string, paymentData: PaymentConfirmPayload): Promise<AxiosResponse<Booking>> => {
    return api.post(`/bookings/${bookingId}/confirm_payment/`, paymentData);
  },
  
  acceptContract: (bookingId: string, signature: SignaturePayload): Promise<AxiosResponse<Booking>> => {
    return api.post(`/bookings/${bookingId}/accept_contract/`, signature);
  },
  
  cancelBooking: (bookingId: string, reason: string): Promise<AxiosResponse<Booking>> => {
    return api.post(`/bookings/${bookingId}/cancel/`, { reason });
  },
  
  getBookingTimeline: (bookingId: string): Promise<AxiosResponse<TimelineEvent[]>> => {
    return api.get(`/bookings/${bookingId}/timeline/`);
  },
};
```

---

## 6. State Management

### 6.1 Store Configuration

```typescript
// app/store.ts

import { configureStore } from '@reduxjs/toolkit';
import rootReducer from './rootReducer';

export const store = configureStore({
  reducer: rootReducer,
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        // Ignore these action types
        ignoredActions: ['persist/PERSIST'],
      },
    }),
  devTools: import.meta.env.DEV,
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
```

### 6.2 Typed Hooks

```typescript
// app/hooks.ts

import { TypedUseSelectorHook, useDispatch, useSelector } from 'react-redux';
import type { RootState, AppDispatch } from './store';

// Use throughout your app instead of plain `useDispatch` and `useSelector`
export const useAppDispatch = () => useDispatch<AppDispatch>();
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;
```

---

## 7. Routing

### 7.1 Route Configuration

```typescript
// routes/index.tsx

import { createBrowserRouter } from 'react-router-dom';
import { protectedRoutes } from './protected';
import { publicRoutes } from './public';
import { adminRoutes } from './admin';
import { Layout } from '../components/layout/Layout';
import { LoadingScreen } from '../components/common/LoadingScreen';
import { useAuth } from '../hooks/useAuth';

export function AppRouter() {
  const { isAuthenticated, isLoading } = useAuth();
  
  if (isLoading) {
    return <LoadingScreen />;
  }
  
  const router = createBrowserRouter([
    ...publicRoutes,
    {
      element: <Layout />,
      children: [
        ...protectedRoutes,
        ...adminRoutes,
      ],
    },
    {
      path: '*',
      element: <NotFoundPage />,
    },
  ]);
  
  return router;
}
```

### 7.2 Route Definitions

```typescript
// routes/protected.tsx

import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { DashboardLayout } from '../components/layout/DashboardLayout';
import { BookingsPage } from '../features/bookings/pages/BookingsPage';
import { BookingDetailPage } from '../features/bookings/pages/BookingDetailPage';
import { AssetsPage } from '../features/assets/pages/AssetsPage';
import { AssetDetailPage } from '../features/assets/pages/AssetDetailPage';

export const protectedRoutes = [
  {
    element: <DashboardLayout />,
    children: [
      {
        path: '/',
        element: <Navigate to="/dashboard" replace />,
      },
      {
        path: '/dashboard',
        element: <DashboardPage />,
      },
      {
        path: '/bookings',
        children: [
          {
            index: true,
            element: <BookingsPage />,
          },
          {
            path: ':id',
            element: <BookingDetailPage />,
          },
        ],
      },
      {
        path: '/assets',
        children: [
          {
            index: true,
            element: <AssetsPage />,
          },
          {
            path: ':id',
            element: <AssetDetailPage />,
          },
        ],
      },
      // ... more routes
    ],
  },
];
```

---

## 8. WebSocket Integration

### 8.1 WebSocket Hook

```typescript
// hooks/useWebSocket.ts

import { useEffect, useCallback, useRef } from 'react';
import { useDispatch } from 'react-redux';
import { Client, IMessage } from '@stomp/stompjs';
import { setNotifications } from '../features/notifications/slice';
import { addMessage } from '../features/messaging/slice';

export function useWebSocket(userId: string) {
  const dispatch = useDispatch();
  const clientRef = useRef<Client | null>(null);
  
  useEffect(() => {
    const client = new Client({
      brokerURL: import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws',
      reconnectDelay: 5000,
      heartbeatIncoming: 4000,
      heartbeatOutgoing: 4000,
      onConnect: () => {
        // Subscribe to user-specific channels
        client.subscribe(`/user/${userId}/notifications`, (message: IMessage) => {
          const notification = JSON.parse(message.body);
          dispatch(setNotifications([notification]));
        });
        
        client.subscribe(`/user/${userId}/messages`, (message: IMessage) => {
          const chatMessage = JSON.parse(message.body);
          dispatch(addMessage(chatMessage));
        });
      },
    });
    
    client.activate();
    clientRef.current = client;
    
    return () => {
      client.deactivate();
    };
  }, [userId, dispatch]);
  
  const sendMessage = useCallback((destination: string, body: object) => {
    if (clientRef.current?.connected) {
      clientRef.current.publish({
        destination,
        body: JSON.stringify(body),
      });
    }
  }, []);
  
  return { sendMessage };
}
```

---

## 9. Authentication Flow

### 9.1 Auth Provider

```typescript
// providers/AuthProvider.tsx

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../services/auth';
import { useToast } from '../hooks/useToast';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginPayload) => Promise<void>;
  logout: () => void;
  register: (data: RegisterPayload) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();
  const toast = useToast();
  
  useEffect(() => {
    // Check for existing session
    const checkAuth = async () => {
      const token = localStorage.getItem('accessToken');
      if (token) {
        try {
          const response = await authApi.getCurrentUser();
          setUser(response.data);
        } catch (error) {
          localStorage.removeItem('accessToken');
          localStorage.removeItem('refreshToken');
        }
      }
      setIsLoading(false);
    };
    
    checkAuth();
  }, []);
  
  const login = async (credentials: LoginPayload) => {
    const response = await authApi.login(credentials);
    const { access, refresh, user: userData } = response.data;
    
    localStorage.setItem('accessToken', access);
    localStorage.setItem('refreshToken', refresh);
    setUser(userData);
    
    toast.success('Welcome back!');
    navigate('/dashboard');
  };
  
  const logout = () => {
    authApi.logout();
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    setUser(null);
    navigate('/login');
  };
  
  const register = async (data: RegisterPayload) => {
    await authApi.register(data);
    toast.success('Registration successful! Please log in.');
    navigate('/login');
  };
  
  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated: !!user,
      isLoading,
      login,
      logout,
      register,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
```

---

## 10. Performance Optimization

### 10.1 Code Splitting

```typescript
// App.tsx

import { Suspense, lazy } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from './providers/AuthProvider';
import { LoadingScreen } from './components/common/LoadingScreen';

const Dashboard = lazy(() => import('./features/dashboard/DashboardPage'));
const Bookings = lazy(() => import('./features/bookings/BookingsPage'));
const Assets = lazy(() => import('./features/assets/AssetsPage'));

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Suspense fallback={<LoadingScreen />}>
          <Routes>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/bookings/*" element={<Bookings />} />
            <Route path="/assets/*" element={<Assets />} />
          </Routes>
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
```

### 10.2 Virtual List (for large lists)

```typescript
// components/common/VirtualList.tsx

import { useVirtualizer } from '@tanstack/react-virtual';

interface VirtualListProps<T> {
  items: T[];
  renderItem: (item: T) => React.ReactNode;
  itemHeight: number;
  overscan?: number;
}

export function VirtualList<T>({ items, renderItem, itemHeight, overscan = 3 }: VirtualListProps<T>) {
  const parentRef = useRef<HTMLDivElement>(null);
  
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => itemHeight,
    overscan,
  });
  
  return (
    <div ref={parentRef} className="h-full overflow-auto">
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        {virtualizer.getVirtualItems().map((virtualItem) => (
          <div
            key={virtualItem.key}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: `${virtualItem.size}px`,
              transform: `translateY(${virtualItem.start}px)`,
            }}
          >
            {renderItem(items[virtualItem.index])}
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## 11. Testing Strategy

### 11.1 Jest Configuration

```typescript
// jest.config.ts

export default {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/tests/setup.ts'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
  },
  transform: {
    '^.+\\.tsx?$': ['ts-jest', {
      tsconfig: 'tsconfig.app.json',
    }],
  },
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/**/*.stories.tsx',
  ],
};
```

### 11.2 Component Test Example

```typescript
// components/forms/Input.test.tsx

import { render, screen, fireEvent } from '@testing-library/react';
import { Input } from './Input';

describe('Input', () => {
  it('renders label and input', () => {
    render(<Input label="Email" placeholder="Enter email" />);
    
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Enter email')).toBeInTheDocument();
  });
  
  it('shows error message', () => {
    render(<Input label="Email" error="Invalid email" />);
    
    expect(screen.getByText('Invalid email')).toHaveClass('text-red-600');
  });
  
  it('calls onChange', () => {
    const handleChange = jest.fn();
    render(<Input onChange={handleChange} />);
    
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'test' } });
    
    expect(handleChange).toHaveBeenCalledWith('test');
  });
});
```

---

## 12. Environment Configuration

### 12.1 Environment Variables

```env
# .env.example

VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws
VITE_APP_NAME=KIBOSS
VITE_APP_VERSION=1.0.0

# Optional: Google Maps API Key
VITE_GOOGLE_MAPS_API_KEY=your_api_key

# Optional: Analytics
VITE_ANALYTICS_ID=your_analytics_id
```

### 12.2 TypeScript Config

```json
// tsconfig.json

{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```
