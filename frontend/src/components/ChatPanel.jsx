import { useState, useRef, useEffect } from 'react'
import { streamChat } from '../api.js'

const TOOL_LABELS = {
  add_stock: 'Fetching stock data...',
  remove_stock: 'Updating chart...',
  clear_chart: 'Updating chart...',
  get_stock_price: 'Looking up price...',
}

const panelStyles = `
  @keyframes pulse-opacity {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.35; }
  }
  .tool-activity {
    animation: pulse-opacity 1.4s ease-in-out infinite;
    font-style: italic;
    font-size: 0.78rem;
    color: #94a3b8;
    padding: 2px 8px;
  }
  .msg-list::-webkit-scrollbar { width: 4px; }
  .msg-list::-webkit-scrollbar-track { background: transparent; }
  .msg-list::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 2px; }
`

function ToolIndicator({ label }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px', paddingLeft: '4px' }}>
      <span className="tool-activity">⏳ {label}</span>
    </div>
  )
}

function MessageBubble({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start',
        marginBottom: '12px',
      }}
    >
      <div
        style={{
          maxWidth: '85%',
          padding: '10px 14px',
          borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
          background: isUser ? '#2563eb' : '#f1f5f9',
          color: isUser ? 'white' : '#1e293b',
          fontSize: '0.9rem',
          lineHeight: '1.5',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {msg.content || (msg.isStreaming ? '▌' : '')}
      </div>
      {msg.toolActivity && <ToolIndicator label={msg.toolActivity} />}
    </div>
  )
}

export default function ChatPanel({ stocks, onChartUpdate }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Hello! I can help you analyze stocks and make predictions. Try asking me to "Add AAPL" or "Show me NVDA forecast".',
    },
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function autoResize() {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    const lineHeight = 22
    const maxHeight = lineHeight * 3 + 16
    ta.style.height = Math.min(ta.scrollHeight, maxHeight) + 'px'
  }

  async function handleSend() {
    const text = input.trim()
    if (!text || isLoading) return

    const userMsg = { role: 'user', content: text }
    const updatedMessages = [...messages, userMsg]

    setMessages(updatedMessages)
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    setIsLoading(true)

    // Add placeholder assistant message
    const assistantIndex = updatedMessages.length
    setMessages(prev => [
      ...prev,
      { role: 'assistant', content: '', isStreaming: true, toolActivity: null },
    ])

    try {
      // Build messages array for API (exclude the streaming placeholder)
      const apiMessages = updatedMessages.map(m => ({ role: m.role, content: m.content }))

      for await (const event of streamChat(apiMessages)) {
        if (event.type === 'text_delta') {
          setMessages(prev => {
            const next = [...prev]
            const msg = { ...next[assistantIndex] }
            msg.content += event.content
            next[assistantIndex] = msg
            return next
          })
        } else if (event.type === 'tool_start') {
          const label = TOOL_LABELS[event.name] || 'Working...'
          setMessages(prev => {
            const next = [...prev]
            next[assistantIndex] = { ...next[assistantIndex], toolActivity: label }
            return next
          })
        } else if (event.type === 'chart_update') {
          onChartUpdate(event)
          // Clear tool activity after chart update
          setMessages(prev => {
            const next = [...prev]
            next[assistantIndex] = { ...next[assistantIndex], toolActivity: null }
            return next
          })
        } else if (event.type === 'tool_error') {
          setMessages(prev => {
            const next = [...prev]
            const msg = { ...next[assistantIndex] }
            msg.content += `\n\nError: ${event.error}`
            msg.toolActivity = null
            next[assistantIndex] = msg
            return next
          })
        } else if (event.type === 'done') {
          setMessages(prev => {
            const next = [...prev]
            next[assistantIndex] = {
              ...next[assistantIndex],
              isStreaming: false,
              toolActivity: null,
            }
            return next
          })
        }
      }
    } catch (err) {
      setMessages(prev => {
        const next = [...prev]
        next[assistantIndex] = {
          role: 'assistant',
          content: `Sorry, I encountered an error: ${err.message}`,
          isStreaming: false,
          toolActivity: null,
        }
        return next
      })
    } finally {
      setIsLoading(false)
      setMessages(prev => {
        const next = [...prev]
        if (next[assistantIndex]) {
          next[assistantIndex] = { ...next[assistantIndex], isStreaming: false, toolActivity: null }
        }
        return next
      })
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <style>{panelStyles}</style>

      {/* Header */}
      <div
        style={{
          background: 'linear-gradient(135deg, #1e293b 0%, #334155 100%)',
          color: 'white',
          padding: '18px 20px',
          fontWeight: 600,
          fontSize: '1.05rem',
          letterSpacing: '0.02em',
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          borderBottom: '2px solid #2563eb',
        }}
      >
        <span style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '32px',
          height: '32px',
          borderRadius: '8px',
          background: 'rgba(37, 99, 235, 0.25)',
          fontSize: '1.1rem',
        }}>
          📈
        </span>
        <div>
          <div>Stock Assistant</div>
          <div style={{ fontSize: '0.7rem', fontWeight: 400, opacity: 0.6, marginTop: '2px' }}>
            Powered by Claude
          </div>
        </div>
      </div>

      {/* Messages */}
      <div
        className="msg-list"
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '16px',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {messages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div
        style={{
          padding: '16px 20px',
          borderTop: '1px solid #e2e8f0',
          background: '#f8fafc',
          flexShrink: 0,
        }}
      >
        <div
          style={{
            display: 'flex',
            gap: '10px',
            alignItems: 'flex-end',
          }}
        >
          <textarea
            ref={textareaRef}
            value={input}
            onChange={e => {
              setInput(e.target.value)
              autoResize()
            }}
            onKeyDown={handleKeyDown}
            placeholder="Ask about a stock..."
            rows={2}
            style={{
              flex: 1,
              resize: 'none',
              border: '1px solid #cbd5e1',
              borderRadius: '12px',
              padding: '12px 16px',
              fontSize: '0.9rem',
              fontFamily: 'inherit',
              outline: 'none',
              lineHeight: '1.5',
              maxHeight: '100px',
              overflowY: 'auto',
              transition: 'border-color 0.15s, box-shadow 0.15s',
              boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
              background: 'white',
            }}
            onFocus={e => { e.target.style.borderColor = '#2563eb'; e.target.style.boxShadow = '0 0 0 3px rgba(37,99,235,0.1)' }}
            onBlur={e => { e.target.style.borderColor = '#cbd5e1'; e.target.style.boxShadow = '0 1px 2px rgba(0,0,0,0.04)' }}
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            style={{
              background: isLoading || !input.trim() ? '#93c5fd' : '#2563eb',
              color: 'white',
              border: 'none',
              borderRadius: '12px',
              padding: '0 20px',
              fontSize: '0.9rem',
              fontWeight: 600,
              cursor: isLoading || !input.trim() ? 'not-allowed' : 'pointer',
              flexShrink: 0,
              transition: 'background 0.15s',
              height: '52px',
            }}
          >
            {isLoading ? '...' : 'Send'}
          </button>
        </div>
        <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '6px', textAlign: 'center' }}>
          Enter to send · Shift+Enter for new line
        </div>
      </div>
    </div>
  )
}
