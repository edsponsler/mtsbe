"use client";

import { useState } from "react";

// Types corresponding to our API
interface SourceContext {
  id: string;
  title: string;
  text: string;
  hebrew_text: string;
  midrash_links: string[];
}

interface NarrativeResponse {
  share_id?: string;
  narrative: string;
  sources: SourceContext[];
}

export default function Home() {
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<NarrativeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch("http://127.0.0.1:8000/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: query.trim(),
          num_results: 3,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(errData?.detail || `Server error: ${res.status}`);
      }

      const data: NarrativeResponse = await res.json();
      setResult(data);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "An unexpected error occurred while fetching the narrative.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="container">
      <header className="header">
        <h1 className="title">MTSBE</h1>
        <h2 className="subtitle">Multi-Tradition Semantic Bible Engine</h2>
      </header>

      <div className="search-container">
        <form className="search-form" onSubmit={handleSearch}>
          <input
            type="text"
            className="search-input"
            placeholder="Explore the scriptures... (e.g., Adam and Eve biting the apple)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={isLoading}
          />
          <button 
            type="submit" 
            className="search-button"
            disabled={isLoading || !query.trim()}
          >
            Seek
          </button>
        </form>
      </div>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      {isLoading && (
        <div className="loader-container">
          <div className="spinner"></div>
          <div className="loader-text">Consulting the ancient texts...</div>
        </div>
      )}

      {result && !isLoading && (
        <div className="results-container">
          <div className="narrative-card">
            <h3 className="narrative-title">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
              </svg>
              Synthesized Narrative
            </h3>
            {result.share_id && (
              <button 
                className="search-button" 
                style={{ position: 'absolute', top: '2rem', right: '2rem', padding: '0.5rem 1rem', fontSize: '0.9rem' }}
                onClick={() => {
                  const url = `${window.location.origin}/share/${result.share_id}`;
                  navigator.clipboard.writeText(url);
                  alert(`Copied link to clipboard: ${url}`);
                }}
              >
                Copy Share Link
              </button>
            )}
            <div className="narrative-content">
              {result.narrative.split("\n\n").map((para, i) => (
                <p key={i}>{para}</p>
              ))}
            </div>
          </div>

          <aside className="sources-container">
            <h4 className="sources-header">Canonical Sources</h4>
            {result.sources.map((source, index) => (
              <div key={index} className="source-card">
                <h5 className="source-title">{source.title}</h5>
                <span className="source-id">{source.id}</span>
                <p className="source-text">{source.text}</p>
                {source.hebrew_text && (
                  <details style={{marginTop: '1rem', cursor: 'pointer', fontSize: '0.85rem', color: 'rgba(212, 175, 55, 0.8)'}}>
                    <summary style={{fontWeight: '500'}}>View Original Language</summary>
                    <p style={{marginTop: '0.5rem', fontFamily: 'serif', direction: 'rtl', textAlign: 'right', fontSize: '1.2rem', lineHeight: '1.6'}}>{source.hebrew_text}</p>
                  </details>
                )}
              </div>
            ))}
          </aside>
        </div>
      )}
    </main>
  );
}
