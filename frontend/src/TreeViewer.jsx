import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Download, ExternalLink, Image as ImageIcon, Maximize, ZoomIn, ZoomOut } from 'lucide-react'

const MIN_ZOOM = 0.05
const MAX_ZOOM = 4

// Pan/zoom viewer for a (very large) poster SVG, with SVG and PNG export.
export default function TreeViewer({ src, title }) {
  const frame = useRef(null)
  const drag = useRef(null)
  const [size, setSize] = useState(null) // natural size from the SVG viewBox
  const [view, setView] = useState({ zoom: 1, x: 0, y: 0 })
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    let cancelled = false
    setSize(null)
    fetch(src)
      .then((r) => r.text())
      .then((text) => {
        const m = text.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/)
        if (!cancelled && m) setSize({ w: +m[1], h: +m[2] })
      })
    return () => { cancelled = true }
  }, [src])

  const fit = useCallback(() => {
    if (!size || !frame.current) return
    const { clientWidth: fw, clientHeight: fh } = frame.current
    const zoom = Math.min(fw / size.w, fh / size.h) * 0.96
    setView({ zoom, x: (fw - size.w * zoom) / 2, y: (fh - size.h * zoom) / 2 })
  }, [size])

  useEffect(() => { fit() }, [fit])

  const zoomAt = (factor, cx, cy) => {
    setView((v) => {
      const zoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, v.zoom * factor))
      const k = zoom / v.zoom
      return { zoom, x: cx - (cx - v.x) * k, y: cy - (cy - v.y) * k }
    })
  }

  const zoomCentre = (factor) => {
    const el = frame.current
    zoomAt(factor, el.clientWidth / 2, el.clientHeight / 2)
  }

  useEffect(() => {
    const el = frame.current
    if (!el) return
    const onWheel = (e) => {
      e.preventDefault()
      const rect = el.getBoundingClientRect()
      zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX - rect.left, e.clientY - rect.top)
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  const onPointerDown = (e) => {
    drag.current = { x: e.clientX, y: e.clientY }
    e.currentTarget.setPointerCapture(e.pointerId)
  }
  const onPointerMove = (e) => {
    if (!drag.current) return
    const dx = e.clientX - drag.current.x
    const dy = e.clientY - drag.current.y
    drag.current = { x: e.clientX, y: e.clientY }
    setView((v) => ({ ...v, x: v.x + dx, y: v.y + dy }))
  }
  const onPointerUp = () => { drag.current = null }

  const fileName = (title || 'rock-family-tree').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')

  const downloadSvg = async () => {
    const blob = await (await fetch(src)).blob()
    save(blob, `${fileName}.svg`)
  }

  const downloadPng = async (scale) => {
    if (!size) return
    setExporting(true)
    try {
      const text = await (await fetch(src)).text()
      const url = URL.createObjectURL(new Blob([text], { type: 'image/svg+xml' }))
      const img = new Image()
      await new Promise((resolve, reject) => { img.onload = resolve; img.onerror = reject; img.src = url })
      const canvas = document.createElement('canvas')
      canvas.width = Math.round(size.w * scale)
      canvas.height = Math.round(size.h * scale)
      canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height)
      URL.revokeObjectURL(url)
      canvas.toBlob((blob) => save(blob, `${fileName}.png`), 'image/png')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="relative w-full h-full">
      <div
        ref={frame}
        className="absolute inset-0 overflow-hidden cursor-grab active:cursor-grabbing select-none touch-none"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onDoubleClick={fit}
      >
        {size && (
          <img
            src={src}
            alt={title || 'Rock family tree'}
            draggable={false}
            style={{
              position: 'absolute', left: 0, top: 0,
              width: size.w, height: size.h, maxWidth: 'none',
              transformOrigin: '0 0',
              transform: `translate(${view.x}px, ${view.y}px) scale(${view.zoom})`,
              boxShadow: '0 4px 24px rgba(0,0,0,0.25)',
            }}
          />
        )}
      </div>

      <div className="absolute top-3 right-3 flex flex-col gap-2">
        <ToolButton label="Zoom in" onClick={() => zoomCentre(1.3)}><ZoomIn className="w-5 h-5" /></ToolButton>
        <ToolButton label="Zoom out" onClick={() => zoomCentre(1 / 1.3)}><ZoomOut className="w-5 h-5" /></ToolButton>
        <ToolButton label="Fit to screen" onClick={fit}><Maximize className="w-5 h-5" /></ToolButton>
      </div>

      <div className="absolute bottom-3 right-3 flex gap-2">
        <ToolButton label="Open full size in a new tab" onClick={() => window.open(src, '_blank')}>
          <ExternalLink className="w-5 h-5" />
        </ToolButton>
        <ToolButton label="Download PNG (2x)" onClick={() => downloadPng(2)} disabled={exporting}>
          <ImageIcon className="w-5 h-5" /><span className="text-sm">PNG</span>
        </ToolButton>
        <ToolButton label="Download SVG (print quality)" onClick={downloadSvg}>
          <Download className="w-5 h-5" /><span className="text-sm">SVG</span>
        </ToolButton>
      </div>

      {size && (
        <div className="absolute bottom-3 left-3 text-xs text-text-secondary bg-paper/90 px-2 py-1 border border-border">
          {Math.round(view.zoom * 100)}% · scroll to zoom, drag to pan, double-click to fit
        </div>
      )}
    </div>
  )
}

function ToolButton({ label, children, ...props }) {
  return (
    <button
      title={label}
      aria-label={label}
      className="ink-box flex items-center gap-1 px-2 py-2 hover:bg-white disabled:opacity-50"
      {...props}
    >
      {children}
    </button>
  )
}

function save(blob, name) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)
}
