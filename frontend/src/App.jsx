import { useState, useEffect } from 'react'
import StockChart from './components/StockChart.jsx'
import ChatPanel from './components/ChatPanel.jsx'
import { fetchDefaults } from './api.js'

const globalStyles = `
  * { box-sizing: border-box; }
  body { margin: 0; font-family: system-ui, -apple-system, sans-serif; background: #f8fafc; }
  #root { height: 100vh; overflow: hidden; }
`

export default function App() {
  const [stocks, setStocks] = useState({})

  useEffect(() => {
    fetchDefaults()
      .then(data => {
        if (Array.isArray(data)) {
          const obj = {}
          data.forEach(s => { obj[s.ticker] = s })
          setStocks(obj)
        }
      })
      .catch(() => {
        // Backend not yet running — start with empty state
      })
  }, [])

  function handleChartUpdate(event) {
    setStocks(prev => {
      const next = { ...prev }
      if (event.action === 'add') {
        next[event.ticker] = event.data
      } else if (event.action === 'remove') {
        delete next[event.ticker]
      } else if (event.action === 'clear') {
        return {}
      }
      return next
    })
  }

  return (
    <>
      <style>{globalStyles}</style>
      <div style={{ display: 'flex', height: '100vh' }}>
        <div
          style={{
            flex: '65',
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
            background: 'white',
          }}
        >
          <StockChart stocks={stocks} />
        </div>
        <div
          style={{
            width: '380px',
            flexShrink: 0,
            borderLeft: '1px solid #e2e8f0',
            display: 'flex',
            flexDirection: 'column',
            background: 'white',
          }}
        >
          <ChatPanel stocks={stocks} onChartUpdate={handleChartUpdate} />
        </div>
      </div>
    </>
  )
}
