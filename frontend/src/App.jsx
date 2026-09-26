import React, { useEffect, useRef, useState } from 'react'
import { History, Loader2, Search, Sparkles, Wand2, X } from 'lucide-react'

import { apiUrl, errorMessage, getStatus, listSamples, searchArtists, startGeneration } from './api'
import { phrases } from './phrases'
import TreeViewer from './TreeViewer'

const DEPTH_HELP = {
  1: 'Just this band and its line-ups',
  2: 'Plus every band its members went on to (recommended)',
  3: 'Plus the bands those musicians played in',
  4: 'Sprawling — can take several minutes',
}

const RECENT_KEY = 'rftg.recent'

function loadRecent() {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY)) || [] } catch { return [] }
}

function saveRecent(list) {
  try { localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, 8))) } catch { /* private mode */ }
}

export default function App() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [selected, setSelected] = useState(null)
  const [samples, setSamples] = useState([])

  const [options, setOptions] = useState({
    depth: 2, max_bands: 24, title: '', paper: 'A1',
    hand_drawn: true, coloured_lines: false, refresh: false,
  })
  const [job, setJob] = useState(null) // latest status payload
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null) // { url, title, stats }
  const [recent, setRecent] = useState(loadRecent)
  const [phrase, setPhrase] = useState(phrases[0])
  const pollTimer = useRef(null)

  const generating = job && (job.status === 'Pending' || job.status === 'Processing')

  useEffect(() => { listSamples().then(setSamples).catch(() => {}) }, [])

  useEffect(() => {
    if (!generating) return
    const t = setInterval(() => setPhrase(phrases[Math.floor(Math.random() * phrases.length)]), 6000)
    return () => clearInterval(t)
  }, [generating])

  useEffect(() => () => clearTimeout(pollTimer.current), [])

  const setOption = (key, value) => setOptions((o) => ({ ...o, [key]: value }))

  const doSearch = async (e) => {
    e?.preventDefault()
    if (!query.trim()) return
    setSearching(true)
    setError(null)
    setSelected(null)
    try {
      const found = await searchArtists(query.trim())
      setResults(found)
      if (!found.length) setError(`Nothing found for “${query}”`)
    } catch (err) {
      setResults([])
      setError(errorMessage(err))
    } finally {
      setSearching(false)
    }
  }

  const choose = (artist) => {
    setSelected(artist)
    setResults([])
    const sample = samples.find((s) => s.id === artist.id)
    if (sample) setOption('depth', sample.default_depth)
  }

  const poll = (jobId, subject) => {
    pollTimer.current = setTimeout(async () => {
      try {
        const status = await getStatus(jobId)
        setJob(status)
        if (status.status === 'Completed') {
          const entry = {
            jobId, name: subject.name, title: status.title, stats: status.stats,
            url: apiUrl(status.result_url), when: Date.now(),
          }
          setResult(entry)
          setRecent((prev) => {
            const next = [entry, ...prev.filter((r) => r.jobId !== jobId)]
            saveRecent(next)
            return next
          })
        } else if (status.status === 'Error') {
          setError(status.message || 'Generation failed')
        } else {
          poll(jobId, subject)
        }
      } catch (err) {
        setError(errorMessage(err))
        setJob(null)
      }
    }, 1200)
  }

  const generate = async (subject = selected, overrides = {}) => {
    if (!subject || generating) return
    setError(null)
    clearTimeout(pollTimer.current)
    const body = { ...options, ...overrides, artist_id: subject.id, title: options.title.trim() || null }
    try {
      const started = await startGeneration(body)
      setJob(started)
      poll(started.job_id, subject)
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  const tryDemo = (sample) => {
    const subject = { id: sample.id, name: sample.name }
    setSelected(subject)
    setOption('depth', sample.default_depth)
    generate(subject, { depth: sample.default_depth }) // state updates are async
  }

  return (
    <div className="h-screen flex flex-col bg-background text-text-primary font-sans">
      <header className="border-b-2 border-border px-6 py-3 flex items-baseline gap-4 bg-paper">
        <h1 className="text-2xl font-serif tracking-wide">Rock Family Tree Generator</h1>
        <p className="text-sm text-text-secondary hidden md:block">
          Hand-drawn style band genealogies, after Pete Frame — from MusicBrainz data
        </p>
      </header>

      <div className="flex-1 flex flex-col md:flex-row min-h-0">
        <aside className="md:w-96 shrink-0 overflow-y-auto p-4 space-y-4 border-r-2 border-border">
          <section className="ink-box p-4 space-y-3">
            <h2 className="font-marker text-lg">1. Pick a band</h2>
            <form onSubmit={doSearch} className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-text-secondary" />
                <input
                  type="text"
                  placeholder="e.g. Fleetwood Mac"
                  className="w-full pl-8 pr-2 py-2 border-2 border-border bg-white focus:outline-none"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>
              <button className="px-3 py-2 bg-accent text-paper hover:bg-accent-hover disabled:opacity-50"
                      disabled={searching || !query.trim()}>
                {searching ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Search'}
              </button>
            </form>

            {results.length > 0 && (
              <ul className="max-h-72 overflow-y-auto border-2 border-border bg-white divide-y divide-border/20">
                {results.map((a) => (
                  <li key={a.id}>
                    <button onClick={() => choose(a)} className="w-full text-left px-3 py-2 hover:bg-background">
                      <span className="font-bold">{a.name}</span>
                      <span className="text-xs text-text-secondary">
                        {' '}{[a.type, a.country, a.years].filter(Boolean).join(' · ')}
                      </span>
                      {a.disambiguation && <p className="text-xs text-text-secondary">{a.disambiguation}</p>}
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {selected && (
              <div className="flex items-center justify-between border-2 border-border bg-white px-3 py-2">
                <span className="font-bold truncate">{selected.name}</span>
                <button onClick={() => setSelected(null)} aria-label="Clear selection"><X className="w-4 h-4" /></button>
              </div>
            )}

            {samples.map((s) => (
              <button key={s.id} onClick={() => tryDemo(s)} disabled={generating}
                      className="w-full flex items-center gap-2 text-left text-sm px-3 py-2 border-2 border-dashed border-border hover:bg-white disabled:opacity-50">
                <Sparkles className="w-4 h-4 shrink-0" />
                <span>No network? Try the offline demo: <b>{s.name.replace(' (demo)', '')}</b></span>
              </button>
            ))}
          </section>

          <section className="ink-box p-4 space-y-3">
            <h2 className="font-marker text-lg">2. Set it up</h2>
            <label className="block text-sm">
              How far to branch out: <b>{options.depth}</b>
              <input type="range" min="1" max="4" value={options.depth} className="w-full"
                     onChange={(e) => setOption('depth', +e.target.value)} />
              <span className="text-xs text-text-secondary">{DEPTH_HELP[options.depth]}</span>
            </label>
            <label className="block text-sm">
              Maximum bands on the poster: <b>{options.max_bands}</b>
              <input type="range" min="3" max="60" value={options.max_bands} className="w-full"
                     onChange={(e) => setOption('max_bands', +e.target.value)} />
            </label>
            <label className="block text-sm">
              Title (optional)
              <input type="text" value={options.title} placeholder="THE … FAMILY TREE" maxLength={120}
                     onChange={(e) => setOption('title', e.target.value)}
                     className="w-full mt-1 px-2 py-1 border-2 border-border bg-white" />
            </label>
            <label className="block text-sm">
              Paper
              <select value={options.paper} onChange={(e) => setOption('paper', e.target.value)}
                      className="w-full mt-1 px-2 py-1 border-2 border-border bg-white">
                {['A0', 'A1', 'A2', 'A3', 'A4'].map((p) => <option key={p} value={p}>{p} poster</option>)}
                <option value="none">Fit to content</option>
              </select>
            </label>
            <Toggle label="Hand-drawn wobble" checked={options.hand_drawn} onChange={(v) => setOption('hand_drawn', v)} />
            <Toggle label="Colour each musician's lines" checked={options.coloured_lines} onChange={(v) => setOption('coloured_lines', v)} />
            <Toggle label="Ignore cache (re-fetch from MusicBrainz)" checked={options.refresh} onChange={(v) => setOption('refresh', v)} />
          </section>

          <button
            onClick={() => generate()}
            disabled={!selected || generating}
            className="w-full ink-box py-3 font-marker text-xl flex items-center justify-center gap-2 bg-accent text-paper hover:bg-accent-hover disabled:opacity-40"
          >
            {generating ? <Loader2 className="w-5 h-5 animate-spin" /> : <Wand2 className="w-5 h-5" />}
            {generating ? 'Drawing…' : '3. Draw the tree'}
          </button>

          {error && <p className="ink-box p-3 text-sm border-red-800 text-red-900">{error}</p>}

          {recent.length > 0 && (
            <section className="ink-box p-4">
              <h2 className="font-marker text-lg flex items-center gap-2"><History className="w-4 h-4" />Recent trees</h2>
              <ul className="text-sm mt-2 space-y-1">
                {recent.map((r) => (
                  <li key={r.jobId}>
                    <button className="underline decoration-dotted text-left" onClick={() => setResult(r)}>{r.title || r.name}</button>
                    {r.stats && <span className="text-xs text-text-secondary"> · {r.stats.bands} bands</span>}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </aside>

        <main className="flex-1 min-h-[60vh] relative">
          {generating ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 p-8 text-center">
              <Loader2 className="w-12 h-12 animate-spin" />
              <p className="font-marker text-2xl">{phrase}</p>
              <div className="w-80 max-w-full h-3 border-2 border-border bg-paper">
                <div className="h-full bg-accent transition-all duration-500" style={{ width: `${job.progress || 2}%` }} />
              </div>
              <p className="text-sm text-text-secondary">{job.message}</p>
            </div>
          ) : result ? (
            <TreeViewer key={result.url} src={result.url} title={result.title} />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center p-8">
              <div className="ink-box p-8 max-w-lg text-center space-y-3 rotate-[-1deg]">
                <p className="font-serif text-3xl">Every band has a family tree</p>
                <p>Search for a band, choose how far to follow its members, and the generator will research the
                  line-ups on MusicBrainz and letter them into a poster in the spirit of Pete Frame's classic trees.</p>
                <p className="text-sm text-text-secondary">Big families can take a few minutes the first time —
                  MusicBrainz allows one request per second. After that everything is cached.</p>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

function Toggle({ label, checked, onChange }) {
  return (
    <label className="flex items-center gap-2 text-sm cursor-pointer">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="w-4 h-4 accent-black" />
      {label}
    </label>
  )
}
