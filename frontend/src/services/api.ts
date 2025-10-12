/**
 * API Service
 * Handles HTTP requests to the backend API
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  SymbolsResponse,
  ChartDataResponse,
  HealthStatus,
} from '@/types/chart.types';

class ApiService {
  private client: AxiosInstance;

  constructor(baseURL?: string) {
    this.client = axios.create({
      baseURL: baseURL || import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor for authentication
    this.client.interceptors.request.use(
      (config) => {
        // Add auth token if available
        const token = localStorage.getItem('auth_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response) {
          // Server responded with error
          console.error('API Error:', error.response.status, error.response.data);
        } else if (error.request) {
          // Request made but no response
          console.error('Network Error:', error.message);
        } else {
          // Error in request setup
          console.error('Request Error:', error.message);
        }
        return Promise.reject(error);
      }
    );
  }

  /**
   * Get available symbols grouped by exchange
   */
  async getSymbols(): Promise<SymbolsResponse> {
    try {
      const response = await this.client.get<SymbolsResponse>('/api/v1/symbols');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch symbols:', error);
      throw error;
    }
  }

  /**
   * Get chart data for a symbol
   */
  async getChartData(
    symbol: string,
    timeframe: string,
    limit: number = 1000
  ): Promise<ChartDataResponse> {
    try {
      const response = await this.client.get<ChartDataResponse>(
        `/api/v1/charts/${symbol}`,
        {
          params: { timeframe, limit },
        }
      );
      return response.data;
    } catch (error) {
      console.error('Failed to fetch chart data:', error);
      throw error;
    }
  }

  /**
   * Get system health status
   */
  async getHealth(): Promise<HealthStatus> {
    try {
      const response = await this.client.get<HealthStatus>('/api/v1/health');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch health status:', error);
      throw error;
    }
  }

  /**
   * Get ML features for a symbol
   */
  async getFeatures(
    symbol: string,
    startDate?: string,
    endDate?: string
  ): Promise<any> {
    try {
      const response = await this.client.get(`/api/v1/features/${symbol}`, {
        params: { start_date: startDate, end_date: endDate },
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch features:', error);
      throw error;
    }
  }

  /**
   * Get data quality metrics for a symbol
   */
  async getQuality(symbol: string): Promise<any> {
    try {
      const response = await this.client.get(`/api/v1/quality/${symbol}`);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch quality metrics:', error);
      throw error;
    }
  }

  /**
   * Login user
   */
  async login(username: string, password: string): Promise<{ access_token: string }> {
    try {
      const response = await this.client.post('/api/v1/auth/login', {
        username,
        password,
      });
      
      // Store token
      if (response.data.access_token) {
        localStorage.setItem('auth_token', response.data.access_token);
      }
      
      return response.data;
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  }

  /**
   * Logout user
   */
  logout(): void {
    localStorage.removeItem('auth_token');
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated(): boolean {
    return !!localStorage.getItem('auth_token');
  }
}

// Export singleton instance
export const apiService = new ApiService();
