// src/hooks/useWebSocket.ts
import { useEffect, useRef, useCallback, useState } from 'react'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'

export function useTransactionStream(onMessage: (tx: any) => void) {
  const ws = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>()

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return

    ws.current = new WebSocket(`${WS_URL}/ws/stream`)

    ws.current.onopen = () => {
      setConnected(true)
      console.log('[WS] Transaction stream connected')
    }

    ws.current.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.type !== 'ping') onMessage(data)
      } catch {}
    }

    ws.current.onclose = () => {
      setConnected(false)
      reconnectTimer.current = setTimeout(connect, 3000)
    }

    ws.current.onerror = () => {
      ws.current?.close()
    }
  }, [onMessage])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      ws.current?.close()
    }
  }, [connect])

  return { connected }
}

export function useAlertStream(onAlert: (alert: any) => void) {
  const ws = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>()

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return

    ws.current = new WebSocket(`${WS_URL}/ws/alerts`)

    ws.current.onopen = () => setConnected(true)
    ws.current.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.type !== 'ping') onAlert(data)
      } catch {}
    }
    ws.current.onclose = () => {
      setConnected(false)
      reconnectTimer.current = setTimeout(connect, 3000)
    }
    ws.current.onerror = () => ws.current?.close()
  }, [onAlert])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      ws.current?.close()
    }
  }, [connect])

  return { connected }
}
