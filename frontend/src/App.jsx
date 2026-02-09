import React, { useState } from 'react'
import axios from 'axios'
import { Search, Download, Settings, Loader2 } from 'lucide-react'

function App() {
  const [query, setQuery] = useState('')
  const [depth, setDepth] = useState(2)
  const [isGenerating, setIsGenerating] = useState(false)
  const [jobId, setJobId] = useState(null)
  const [status, setStatus] = useState(null)
  const [searchResults, setSearchResults] = useState([])
  const [selectedArtist, setSelectedArtist] = useState(null)

  const handleSearch = async () => {
    if (!query) return;
    try {
      const response = await axios.get(`http://localhost:8000/search?q=${query}`)
      setSearchResults(response.data)
    } catch (error) {
      console.error('Search failed:', error)
    }
  }

  const handleGenerate = async () => {
    if (!selectedArtist) return;
    setIsGenerating(true)
    try {
      const response = await axios.post('http://localhost:8000/generate', {
        artist_id: selectedArtist.id,
        depth: depth
      })
      setJobId(response.data.job_id)
      pollStatus(response.data.job_id)
    } catch (error) {
      console.error('Generation failed:', error)
      setIsGenerating(false)
    }
  }

  const pollStatus = (id) => {
    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`http://localhost:8000/status/${id}`)
        setStatus(response.data)
        if (response.data.status === 'Completed' || response.data.status === 'Error') {
          clearInterval(interval)
          setIsGenerating(false)
        }
      } catch (error) {
        console.error('Status poll failed:', error)
        clearInterval(interval)
        setIsGenerating(false)
      }
    }, 2000)
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-bold tracking-tight text-slate-800">
          ROCK FAMILY TREE <span className="text-slate-400">GENERATOR</span>
        </h1>
        <div className="flex items-center gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search band..."
              className="pl-10 pr-4 py-2 bg-slate-100 border-none rounded-full text-sm focus:ring-2 focus:ring-indigo-500 w-64 transition-all"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            />
            {searchResults.length > 0 && !selectedArtist && (
              <div className="absolute top-full mt-2 w-full bg-white shadow-xl rounded-xl border border-slate-200 z-50 overflow-hidden">
                {searchResults.map((artist) => (
                  <button
                    key={artist.id}
                    onClick={() => setSelectedArtist(artist)}
                    className="w-full text-left px-4 py-3 hover:bg-slate-50 border-b border-slate-100 last:border-none"
                  >
                    <p className="text-sm font-bold text-slate-800">{artist.name}</p>
                    {artist.disambiguation && <p className="text-xs text-slate-400">{artist.disambiguation}</p>}
                  </button>
                ))}
              </div>
            )}
            {selectedArtist && (
              <div className="absolute top-full mt-2 w-full bg-indigo-50 border border-indigo-200 rounded-full px-4 py-1 flex items-center justify-between">
                <span className="text-xs font-bold text-indigo-700 truncate">{selectedArtist.name}</span>
                <button onClick={() => setSelectedArtist(null)} className="text-indigo-400 hover:text-indigo-600">×</button>
              </div>
            )}
          </div>
          <button 
            onClick={handleGenerate}
            disabled={isGenerating || !selectedArtist}
            className="bg-indigo-600 text-white px-4 py-2 rounded-full text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-2"
          >
            {isGenerating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Settings className="w-4 h-4" />}
            Generate
          </button>
        </div>
      </header>

      <main className="p-8">
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-8">
          <aside className="space-y-6">
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-4">Configuration</h2>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium block mb-2">Recursion Depth: {depth}</label>
                  <input 
                    type="range" min="1" max="5" 
                    value={depth} 
                    onChange={(e) => setDepth(parseInt(e.target.value))}
                    className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
                  />
                </div>
              </div>
            </div>

            {status && (
              <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-4">Status</h2>
                <div className="space-y-2">
                  <p className="text-sm font-medium">{status.status}</p>
                  <div className="w-full bg-slate-100 rounded-full h-2">
                    <div 
                      className="bg-indigo-600 h-2 rounded-full transition-all duration-500" 
                      style={{ width: `${status.progress}%` }}
                    ></div>
                  </div>
                </div>
              </div>
            )}
          </aside>

          <section className="md:col-span-3">
            <div className="bg-slate-200 aspect-[1/1.414] rounded-xl border-4 border-dashed border-slate-300 flex items-center justify-center relative overflow-hidden group">
              {isGenerating ? (
                <div className="text-center">
                  <Loader2 className="w-12 h-12 text-slate-400 animate-spin mx-auto mb-4" />
                  <p className="text-slate-500 font-medium">Generating your masterpiece...</p>
                </div>
              ) : (
                <div className="text-center group-hover:scale-105 transition-transform duration-500">
                   <p className="text-slate-400 font-medium">Tree Preview Area (A1)</p>
                   <p className="text-slate-300 text-xs mt-2 uppercase tracking-widest">SVG Render Canvas</p>
                </div>
              )}
              
              <button className="absolute bottom-6 right-6 bg-white shadow-lg p-4 rounded-full text-slate-700 hover:text-indigo-600 transition-colors">
                <Download className="w-6 h-6" />
              </button>
            </div>
          </section>
        </div>
      </main>
    </div>
  )
}

export default App
