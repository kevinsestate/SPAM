import { useEffect, useRef, useState } from 'react'

export function useWebSocket(url) {
  const [ws, setWs] = useState(null)
  const reconnectTimeoutRef = useRef(null)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 5

  useEffect(() => {
    let socket = null

    const connect = () => {
      try {
        socket = new WebSocket(url)
        
        socket.onopen = () => {
          console.log('WebSocket connected')
          reconnectAttempts.current = 0
          setWs(socket)
        }

        socket.onerror = (error) => {
          console.error('WebSocket error:', error)
        }

        socket.onclose = () => {
          console.log('WebSocket disconnected')
          setWs(null)
          
          // Attempt to reconnect
          if (reconnectAttempts.current < maxReconnectAttempts) {
            reconnectAttempts.current++
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000)
            reconnectTimeoutRef.current = setTimeout(() => {
              connect()
            }, delay)
          }
        }
      } catch (error) {
        console.error('Failed to create WebSocket:', error)
      }
    }

    connect()

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (socket) {
        socket.close()
      }
    }
  }, [url])

  return ws
}

