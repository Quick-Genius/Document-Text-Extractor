import { useAuth } from '@clerk/clerk-react';
import axios from 'axios';
import { useMemo } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export function useApi() {
  const { getToken } = useAuth();

  const api = useMemo(() => {
    const instance = axios.create({
      baseURL: API_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    instance.interceptors.request.use(async (config) => {
      try {
        const token = await getToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
      } catch (error) {
        console.error('Failed to get auth token:', error);
      }
      return config;
    });

    // Add response interceptor for global error handling
    instance.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          console.error('Unauthorized access - potential session expiry');
        }
        return Promise.reject(error);
      }
    );

    return instance;
  }, [getToken]);

  return api;
}
