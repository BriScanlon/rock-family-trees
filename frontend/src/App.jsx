import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { Search, Download, Settings, Loader2 } from 'lucide-react'

import { phrases } from './phrases';
function App() {
  // Automatically detect backend host based on frontend URL
  const backendPort = import.meta.env.VITE_BACKEND_PORT || 8000;
  const backendHost = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
  const backendUrl = `http://${backendHost}:${backendPort}`;
  console.log('Backend URL:', backendUrl);
  
  const [query, setQuery] = useState('')
  const [depth, setDepth] = useState(2)
  const [isGenerating, setIsGenerating] = useState(false)
  const [jobId, setJobId] = useState(null)
  const [status, setStatus] = useState(null)
  const [resultUrl, setResultUrl] = useState(null)
  const [searchResults, setSearchResults] = useState([])
  const [selectedArtist, setSelectedArtist] = useState(null)
  const [currentPhrase, setCurrentPhrase] = useState(phrases[0]);

  useEffect(() => {
    let phraseInterval;
    if (isGenerating) {
      phraseInterval = setInterval(() => {
        setCurrentPhrase(phrases[Math.floor(Math.random() * phrases.length)]);
      }, 10000);
    }
    return () => clearInterval(phraseInterval);
  }, [isGenerating]);

  const handleSearch = async () => {
    if (!query) return;
    setSelectedArtist(null); // Clear selection to show results dropdown
    try {
      const response = await axios.get(`${backendUrl}/search?q=${query}`)
      setSearchResults(response.data)
    } catch (error) {
      console.error('Search failed:', error)
    }
  }

  const handleGenerate = async () => {
    if (!selectedArtist) return;
    setIsGenerating(true)
    try {
      const response = await axios.post(`${backendUrl}/generate`, {
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
        const response = await axios.get(`${backendUrl}/status/${id}`)
        setStatus(response.data)
        if (response.data.status === 'Completed' || response.data.status === 'Error') {
          clearInterval(interval)
          setIsGenerating(false)
          if (response.data.status === 'Completed') {
            setResultUrl(`${backendUrl}${response.data.result_url}`)
          }
        }
      } catch (error) {
        console.error('Status poll failed:', error)
        clearInterval(interval)
        setIsGenerating(false)
      }
    }, 2000)
  }

  const handleDownload = () => {
    if (resultUrl) {
      window.open(resultUrl, '_blank')
    }
  }

  return (
    <div className="min-h-screen bg-background text-text-primary font-sans">
      <header className="bg-white border-b border-border px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-serif font-bold tracking-tight text-text-primary">
          ROCK FAMILY TREE <span className="text-text-secondary">GENERATOR</span>
        </h1>
        <div className="flex items-center gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-secondary" />
            <input
              type="text"
              placeholder="Search band..."
              className="pl-10 pr-4 py-2 bg-background border-none rounded-full text-sm focus:ring-2 focus:ring-accent w-64 transition-all"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            />
            {searchResults.length > 0 && !selectedArtist && (
              <div className="absolute top-full mt-2 w-full bg-white shadow-xl rounded-xl border border-border z-50 overflow-hidden">
                {searchResults.map((artist) => (
                  <button
                    key={artist.id}
                    onClick={() => setSelectedArtist(artist)}
                    className="w-full text-left px-4 py-3 hover:bg-background border-b border-border last:border-none"
                  >
                    <p className="text-sm font-bold text-text-primary">{artist.name}</p>
                    {artist.disambiguation && <p className="text-xs text-text-secondary">{artist.disambiguation}</p>}
                  </button>
                ))}
              </div>
            )}
            {selectedArtist && (
              <div className="absolute top-full mt-2 w-full bg-accent/10 border border-accent/20 rounded-full px-4 py-1 flex items-center justify-between">
                <span className="text-xs font-bold text-accent truncate">{selectedArtist.name}</span>
                <button onClick={() => setSelectedArtist(null)} className="text-accent/50 hover:text-accent">×</button>
              </div>
            )}
          </div>
          <button 
            onClick={selectedArtist ? handleGenerate : handleSearch}
            disabled={isGenerating || (!selectedArtist && !query)}
            className="bg-accent text-white px-4 py-2 rounded-full text-sm font-medium hover:bg-accent-hover disabled:opacity-50 flex items-center gap-2 min-w-[100px] justify-center"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Generating
              </>
            ) : selectedArtist ? (
              <>
                <Settings className="w-4 h-4" />
                Generate
              </>
            ) : (
              <>
                <Search className="w-4 h-4" />
                Search
              </>
            )}
          </button>
        </div>
      </header>

      <main className="p-8">
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-8">
          <aside className="space-y-6">
            <div className="bg-white p-6 rounded-xl border border-border shadow-sm">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-text-secondary mb-4">Configuration</h2>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium block mb-2">Recursion Depth: {depth}</label>
                  <input 
                    type="range" min="1" max="5" 
                    value={depth} 
                    onChange={(e) => setDepth(parseInt(e.target.value))}
                    className="w-full h-2 bg-background rounded-lg appearance-none cursor-pointer accent-accent"
                  />
                </div>
              </div>
            </div>

            {status && (
              <div className="bg-white p-6 rounded-xl border border-border shadow-sm">
                <h2 className="text-xs font-semibold uppercase tracking-wider text-text-secondary mb-4">Status</h2>
                <div className="space-y-2">
                  <p className="text-sm font-medium">{status.status}</p>
                  <div className="w-full bg-background rounded-full h-2">
                    <div 
                      className="bg-accent h-2 rounded-full transition-all duration-500" 
                      style={{ width: `${status.progress}%` }}
                    ></div>
                  </div>
                </div>
              </div>
            )}
          </aside>

          <section className="md:col-span-3">
            <div className="bg-white aspect-[1/1.414] rounded-xl border-2 border-dashed border-border flex items-center justify-center relative overflow-hidden group">
              {isGenerating ? (
                <div className="text-center">
                  <Loader2 className="w-12 h-12 text-text-secondary animate-spin mx-auto mb-4" />
                  <p className="text-text-secondary font-medium">{currentPhrase}</p>
                </div>
              ) : resultUrl ? (
                <img src={resultUrl} alt="Generated Rock Family Tree" className="w-full h-full object-contain" />
              ) : (
                <div className="text-center group-hover:scale-105 transition-transform duration-500">
                   <p className="text-text-secondary font-medium">Tree Preview Area (A1)</p>
                   <p className="text-text-secondary/50 text-xs mt-2 uppercase tracking-widest">SVG Render Canvas</p>
                </div>
              )}
              
              <button 
                onClick={handleDownload}
                disabled={!resultUrl}
                className="absolute bottom-6 right-6 bg-white shadow-lg p-4 rounded-full text-text-primary hover:text-accent transition-colors disabled:opacity-50"
              >
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
