import { useState, useEffect, useRef, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';

interface WebSocketMessage {
  type: 'progress' | 'job_completed' | 'job_failed' | 'pong';
  jobId: string;
  data: any;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  subscribe: (jobId: string) => void;
  unsubscribe: (jobId: string) => void;
  lastMessage: WebSocketMessage | null;
}

export function useWebSocket(userId: string): UseWebSocketReturn {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const subscribedJobs = useRef<Set<string>>(new Set());
  const reconnectAttempts = useRef(0);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!userId) return;
    connectWebSocket();
    return () => cleanup();
  }, [userId]);

  const connectWebSocket = () => {
    const token = userId;
    const baseUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/api/v1/ws';
    const ws = new WebSocket(`${baseUrl}?token=${token}`);

    ws.onopen = () => {
      setIsConnected(true);
      reconnectAttempts.current = 0;

      // Re-subscribe to any tracked jobs after reconnect
      subscribedJobs.current.forEach(jobId => {
        ws.send(JSON.stringify({ type: 'subscribe', jobId }));
      });

      pingInterval.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }));
        }
      }, 30_000);
    };

    ws.onmessage = (event) => {
      const message: WebSocketMessage = JSON.parse(event.data);
      setLastMessage(message);

      // Invalidate document query so detail page reloads final data automatically
      if (message.type === 'job_completed' || message.type === 'job_failed') {
        queryClient.invalidateQueries({ queryKey: ['document'] });
        queryClient.invalidateQueries({ queryKey: ['documents'] });
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      setIsConnected(false);
      if (pingInterval.current) clearInterval(pingInterval.current);

      if (reconnectAttempts.current < 5) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30_000);
        reconnectTimeout.current = setTimeout(() => {
          reconnectAttempts.current++;
          connectWebSocket();
        }, delay);
      }
    };

    setSocket(ws);
  };

  const subscribe = useCallback((jobId: string) => {
    subscribedJobs.current.add(jobId);
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'subscribe', jobId }));
    }
  }, [socket]);

  const unsubscribe = useCallback((jobId: string) => {
    subscribedJobs.current.delete(jobId);
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'unsubscribe', jobId }));
    }
  }, [socket]);

  const cleanup = () => {
    if (pingInterval.current) clearInterval(pingInterval.current);
    if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
    if (socket) socket.close();
  };

  return { isConnected, subscribe, unsubscribe, lastMessage };
}
