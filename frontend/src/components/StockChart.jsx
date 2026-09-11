import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'

const STOCK_COLORS = [
  { line: '#2E86AB', ma7: '#A23B72', ma30: '#F18F01', pred: '#C73E1D' },
  { line: '#E63946', ma7: '#FF006E', ma30: '#FB5607', pred: '#8338EC' },
  { line: '#06A77D', ma7: '#4CC9F0', ma30: '#F72585', pred: '#06D6A0' },
]

function buildTracesAndAnnotations(stocks) {
  const traces = []
  const annotations = []
  const tickers = Object.keys(stocks)

  tickers.forEach((ticker, i) => {
    const d = stocks[ticker]
    const c = STOCK_COLORS[i % STOCK_COLORS.length]

    // 1. Historical prices — solid line
    traces.push({
      x: d.dates,
      y: d.prices,
      type: 'scatter',
      mode: 'lines',
      name: `${ticker} Price`,
      line: { color: c.line, width: 2 },
      legendgroup: ticker,
      hovertemplate: `%{x}<br>${ticker}: $%{y:.2f}<extra></extra>`,
    })

    // 2. 7-day MA — dashed, hidden from legend by default
    traces.push({
      x: d.dates,
      y: d.ma7,
      type: 'scatter',
      mode: 'lines',
      name: `${ticker} MA7`,
      line: { color: c.ma7, width: 1.5, dash: 'dash' },
      opacity: 0.6,
      legendgroup: `${ticker}_ma`,
      showlegend: false,
      hovertemplate: `%{x}<br>${ticker} MA7: $%{y:.2f}<extra></extra>`,
    })

    // 3. 30-day MA — dashed, hidden from legend by default
    traces.push({
      x: d.dates,
      y: d.ma30,
      type: 'scatter',
      mode: 'lines',
      name: `${ticker} MA30`,
      line: { color: c.ma30, width: 1.5, dash: 'dash' },
      opacity: 0.6,
      legendgroup: `${ticker}_ma`,
      showlegend: false,
      hovertemplate: `%{x}<br>${ticker} MA30: $%{y:.2f}<extra></extra>`,
    })

    // 4. Projection line — dotted from last_date to target_date
    traces.push({
      x: [d.last_date, d.target_date],
      y: [d.current_price, d.predicted_price],
      type: 'scatter',
      mode: 'lines',
      name: `${ticker} Forecast`,
      line: { color: c.pred, width: 2, dash: 'dot' },
      opacity: 0.7,
      legendgroup: ticker,
      hovertemplate: `%{x}<br>${ticker} Forecast: $%{y:.2f}<extra></extra>`,
    })

    // 5. Prediction marker — star at target_date
    traces.push({
      x: [d.target_date],
      y: [d.predicted_price],
      type: 'scatter',
      mode: 'markers',
      name: `${ticker} Target`,
      marker: { color: c.pred, size: 14, symbol: 'star' },
      legendgroup: ticker,
      hovertemplate: `${ticker} Target<br>%{x}<br>$%{y:.2f}<extra></extra>`,
    })

    // Annotation: current → predicted with % change
    const pct = ((d.predicted_price - d.current_price) / d.current_price * 100)
    const sign = pct >= 0 ? '+' : ''
    annotations.push({
      xref: 'paper',
      yref: 'paper',
      x: 1,
      y: 1 - i * 0.12,
      xanchor: 'right',
      yanchor: 'top',
      text: `<b>${ticker}</b>  $${d.current_price.toFixed(2)} → $${d.predicted_price.toFixed(2)} (${sign}${pct.toFixed(1)}%)`,
      showarrow: false,
      font: { size: 12, color: pct >= 0 ? '#16a34a' : '#dc2626' },
      bgcolor: 'rgba(255,255,255,0.85)',
      bordercolor: pct >= 0 ? '#16a34a' : '#dc2626',
      borderwidth: 1,
      borderpad: 4,
    })
  })

  return { traces, annotations }
}

function buildLayout(annotations) {
  return {
    paper_bgcolor: 'white',
    plot_bgcolor: 'white',
    hovermode: 'x unified',
    legend: { orientation: 'h', y: -0.18 },
    xaxis: {
      gridcolor: '#e5e7eb',
      showgrid: true,
      rangeslider: { visible: true },
    },
    yaxis: {
      gridcolor: '#e5e7eb',
      showgrid: true,
      tickprefix: '$',
    },
    margin: { t: 20, r: 20, b: 60, l: 60 },
    annotations,
  }
}

export default function StockChart({ stocks }) {
  const plotRef = useRef(null)
  const initializedRef = useRef(false)

  useEffect(() => {
    if (!plotRef.current) return

    const isEmpty = Object.keys(stocks).length === 0
    if (isEmpty) {
      if (initializedRef.current) {
        Plotly.react(plotRef.current, [], buildLayout([]), { responsive: true })
      }
      return
    }

    const { traces, annotations } = buildTracesAndAnnotations(stocks)
    const layout = buildLayout(annotations)
    const config = { responsive: false, displayModeBar: true, scrollZoom: true }

    if (!initializedRef.current) {
      Plotly.newPlot(plotRef.current, traces, layout, config)
      initializedRef.current = true
    } else {
      Plotly.react(plotRef.current, traces, layout, config)
    }
  }, [stocks])

  // Resize immediately on container size change
  useEffect(() => {
    const el = plotRef.current
    if (!el) return
    const observer = new ResizeObserver(() => {
      if (initializedRef.current) {
        Plotly.Plots.resize(el)
      }
    })
    observer.observe(el)
    return () => {
      observer.disconnect()
      Plotly.purge(el)
    }
  }, [])

  const isEmpty = Object.keys(stocks).length === 0

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative', minHeight: 0 }}>
      {isEmpty && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#94a3b8',
            fontSize: '1.1rem',
            pointerEvents: 'none',
            zIndex: 1,
          }}
        >
          Add stocks via the chat →
        </div>
      )}
      <div
        ref={plotRef}
        style={{ flex: 1, minHeight: 0, width: '100%', height: '100%' }}
      />
    </div>
  )
}
