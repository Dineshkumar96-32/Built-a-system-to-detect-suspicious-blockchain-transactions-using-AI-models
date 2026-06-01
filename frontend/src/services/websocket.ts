// src/services/websocket.ts
import { useStore } from '../store'

const WS_BASE_URL = import.meta.env.VITE_API_URL 
  ? import.meta.env.VITE_API_URL.replace('http', 'ws') 
  : 'ws://localhost:8000'

class WebSocketService {
  private streamSocket: WebSocket | null = null
  private alertSocket: WebSocket | null = null
  private baseReconnectInterval = 2000
  private maxReconnectInterval = 30000
  private streamReconnectAttempts = 0
  private alertReconnectAttempts = 0
  private streamReconnectTimer: ReturnType<typeof setTimeout> | null = null
  private alertReconnectTimer: ReturnType<typeof setTimeout> | null = null
  private isIntentionalDisconnect = false

  connect() {
    this.isIntentionalDisconnect = false
    this.streamReconnectAttempts = 0
    this.alertReconnectAttempts = 0
    this.connectStream()
    this.connectAlerts()
  }

  private connectStream() {
    if (this.streamSocket?.readyState === WebSocket.OPEN || this.streamSocket?.readyState === WebSocket.CONNECTING) return
    if (this.streamReconnectTimer) clearTimeout(this.streamReconnectTimer)

    this.streamSocket = new WebSocket(`${WS_BASE_URL}/ws/stream`)

    this.streamSocket.onopen = () => {
      console.log('Connected to transaction stream')
      useStore.getState().setWsConnected(true)
      this.streamReconnectAttempts = 0
    }

    this.streamSocket.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'ping') {
        this.streamSocket?.send(JSON.stringify({ type: 'pong' }))
        return
      }
      useStore.getState().addTransaction(data)
    }

    this.streamSocket.onclose = (event) => {
      console.log(`Transaction stream disconnected: ${event.code} ${event.reason}`)
      useStore.getState().setWsConnected(false)
      this.streamSocket = null
      
      if (!this.isIntentionalDisconnect) {
        const delay = Math.min(
          this.baseReconnectInterval * Math.pow(1.5, this.streamReconnectAttempts),
          this.maxReconnectInterval
        )
        console.log(`Attempting stream reconnection in ${Math.round(delay)}ms...`)
        this.streamReconnectTimer = setTimeout(() => {
          this.streamReconnectAttempts++
          this.connectStream()
        }, delay)
      }
    }

    this.streamSocket.onerror = (err) => {
      console.error('Transaction stream error:', err)
    }
  }

  private connectAlerts() {
    if (this.alertSocket?.readyState === WebSocket.OPEN || this.alertSocket?.readyState === WebSocket.CONNECTING) return
    if (this.alertReconnectTimer) clearTimeout(this.alertReconnectTimer)

    this.alertSocket = new WebSocket(`${WS_BASE_URL}/ws/alerts`)

    this.alertSocket.onopen = () => {
      console.log('Connected to alert stream')
      this.alertReconnectAttempts = 0
    }

    this.alertSocket.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'ping') {
        this.alertSocket?.send(JSON.stringify({ type: 'pong' }))
        return
      }
      useStore.getState().addAlert(data)
    }

    this.alertSocket.onclose = (event) => {
      console.log(`Alert stream disconnected: ${event.code} ${event.reason}`)
      this.alertSocket = null
      
      if (!this.isIntentionalDisconnect) {
        const delay = Math.min(
          this.baseReconnectInterval * Math.pow(1.5, this.alertReconnectAttempts),
          this.maxReconnectInterval
        )
        this.alertReconnectTimer = setTimeout(() => {
          this.alertReconnectAttempts++
          this.connectAlerts()
        }, delay)
      }
    }
  }

  disconnect() {
    this.isIntentionalDisconnect = true
    if (this.streamReconnectTimer) clearTimeout(this.streamReconnectTimer)
    if (this.alertReconnectTimer) clearTimeout(this.alertReconnectTimer)
    this.streamSocket?.close()
    this.alertSocket?.close()
    this.streamSocket = null
    this.alertSocket = null
    useStore.getState().setWsConnected(false)
  }
}

export const wsService = new WebSocketService()
