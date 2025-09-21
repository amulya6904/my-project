import { useEffect, useRef, useState } from 'react';
import { ProgressUpdate } from '../types/api';

interface UseWebSocketProps {
  url: string;
  onMessage?: (data: ProgressUpdate) => void;
  onError?: (error: Event) => void;
  onClose?: () => void;
}

export const useWebSocket = ({ url, onMessage, onError, onClose }: UseWebSocketProps) => {
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);

  const maxReconnectAttempts = 5;
  const reconnectDelay = 2000;

  const connect = () => {
    try {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        return;
      }

      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setError(null);
        reconnectAttempts.current = 0;
        console.log('WebSocket connected');
      };

      ws.onmessage = (event) => {
        try {
          const data: ProgressUpdate = JSON.parse(event.data);
          onMessage?.(data);
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      ws.onerror = (event) => {
        setError('WebSocket connection error');
        onError?.(event);
      };

      ws.onclose = () => {
        setIsConnected(false);
        wsRef.current = null;
        onClose?.();

        // Attempt to reconnect
        if (reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current++;
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log(`Reconnecting... (${reconnectAttempts.current}/${maxReconnectAttempts})`);
            connect();
          }, reconnectDelay);
        } else {
          setError('Connection lost. Please refresh the page.');
        }
      };
    } catch (err) {
      setError('Failed to create WebSocket connection');
      console.error('WebSocket connection error:', err);
    }
  };

  const disconnect = () => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    
    setIsConnected(false);
    setError(null);
  };

  useEffect(() => {
    if (url) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [url]);

  return {
    isConnected,
    error,
    connect,
    disconnect
  };
};