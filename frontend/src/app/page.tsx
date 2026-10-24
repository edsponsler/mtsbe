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

interface CommentaryContext {
  id: string;
  tradition: string; // 'midrash' | 'patristic' | 'historical'
  author: string;
  work: string;
  reference: string;
  title: string;
  text: string;
  original_language_text?: string | null;
}

interface PerspectiveConfig {
  include_midrash: boolean;
  include_patristic: boolean;
  include_historical: boolean;
  narrative_tone: "dramatic" | "scholarly" | "meditative";
}

interface NarrativeResponse {
  share_id?: string;
  model_used?: string;
  perspectives?: PerspectiveConfig;
  narrative: string;
  sources: SourceContext[];
  commentaries?: CommentaryContext[];
}

export default function Home() {
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [result, setResult] = useState<NarrativeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Perspective Controls State (Priority B)
  const [includeMidrash, setIncludeMidrash] = useState(true);
  const [includePatristic, setIncludePatristic] = useState(true);
  const [includeHistorical, setIncludeHistorical] = useState(true);
  const [narrativeTone, setNarrativeTone] = useState<"dramatic" | "scholarly" | "meditative">("dramatic");

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isLoading || isStreaming) return;

    setIsLoading(true);
    setIsStreaming(false);
    setError(null);
    setResult(null);

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const res = await fetch(`${apiBase}/generate/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: query.trim(),
          num_results: 3,
          perspectives: {
            include_midrash: includeMidrash,
            include_patristic: includePatristic,
            include_historical: includeHistorical,
            narrative_tone: narrativeTone,
          },
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(errData?.detail || `Server error: ${res.status}`);
      }

      if (!res.body) {
        throw new Error("Streaming is not supported by your browser or connection.");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      const processLine = (line: string) => {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data: ")) return;
        const jsonStr = trimmed.slice(6);
        try {
          const event = JSON.parse(jsonStr);
          if (event.type === "metadata") {
            setIsLoading(false);
            setIsStreaming(true);
            setResult({
              share_id: event.share_id,
              model_used: event.model_used,
              perspectives: event.perspectives,
              narrative: "",
              sources: event.sources || [],
              commentaries: event.commentaries || [],
            });
          } else if (event.type === "chunk") {
            setResult((prev) => {
              if (!prev) return prev;
              return {
                ...prev,
                narrative: prev.narrative + (event.text || ""),
              };
            });
          } else if (event.type === "done") {
            setIsStreaming(false);
          } else if (event.type === "error") {
            setError(event.detail || "An error occurred during narrative generation.");
            setIsStreaming(false);
          }
        } catch (e) {
          console.error("Failed to parse SSE line:", line, e);
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          processLine(line);
        }
      }

      if (buffer.trim()) {
        processLine(buffer);
      }
    } catch (err: any) {
      console.error(err);
      setError(err.message || "An unexpected error occurred while fetching the narrative.");
    } finally {
      setIsLoading(false);
      setIsStreaming(false);
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
            placeholder="Explore the scriptures... (e.g., Abraham meets three wandering figures)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={isLoading || isStreaming}
          />
          <button 
            type="submit" 
            className="search-button"
            disabled={isLoading || isStreaming || !query.trim()}
          >
            {isLoading ? "Consulting..." : isStreaming ? "Weaving..." : "Seek"}
          </button>
        </form>
      </div>

      {/* Perspective & Tone Controls Toolbar */}
      <div className="perspectives-toolbar">
        <div className="perspective-row">
          <span className="perspective-label">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
            </svg>
            Tradition Lenses
          </span>
          <div className="perspective-chips">
            <button
              type="button"
              className={`lens-toggle-btn ${includeMidrash ? "active" : ""}`}
              onClick={() => setIncludeMidrash(!includeMidrash)}
              disabled={isLoading || isStreaming}
              title="Toggle Rabbinic Midrash (Midrash Rabbah, Tanchuma, Talmudic Aggadah)"
            >
              <span className="lens-icon">📜</span>
              <span>Midrash</span>
              <span className="lens-status">{includeMidrash ? "ON" : "OFF"}</span>
            </button>

            <button
              type="button"
              className={`lens-toggle-btn ${includePatristic ? "active" : ""}`}
              onClick={() => setIncludePatristic(!includePatristic)}
              disabled={isLoading || isStreaming}
              title="Toggle Patristic Typology (Early Church Fathers, Christological/Sacramental symbols)"
            >
              <span className="lens-icon">✝️</span>
              <span>Patristic</span>
              <span className="lens-status">{includePatristic ? "ON" : "OFF"}</span>
            </button>

            <button
              type="button"
              className={`lens-toggle-btn ${includeHistorical ? "active" : ""}`}
              onClick={() => setIncludeHistorical(!includeHistorical)}
              disabled={isLoading || isStreaming}
              title="Toggle Material & Historical Reality (Flavius Josephus, Roman/Near Eastern context)"
            >
              <span className="lens-icon">🏛️</span>
              <span>Josephus</span>
              <span className="lens-status">{includeHistorical ? "ON" : "OFF"}</span>
            </button>
          </div>
        </div>

        <div className="perspective-row">
          <span className="perspective-label">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            Voice & Tone
          </span>
          <div className="tone-pills">
            <button
              type="button"
              className={`tone-pill ${narrativeTone === "dramatic" ? "active" : ""}`}
              onClick={() => setNarrativeTone("dramatic")}
              disabled={isLoading || isStreaming}
              title="Immersive, evocative literary narrative"
            >
              🎭 Dramatic Story
            </button>
            <button
              type="button"
              className={`tone-pill ${narrativeTone === "scholarly" ? "active" : ""}`}
              onClick={() => setNarrativeTone("scholarly")}
              disabled={isLoading || isStreaming}
              title="Comparative exegetical commentary"
            >
              📖 Scholarly Exegesis
            </button>
            <button
              type="button"
              className={`tone-pill ${narrativeTone === "meditative" ? "active" : ""}`}
              onClick={() => setNarrativeTone("meditative")}
              disabled={isLoading || isStreaming}
              title="Contemplative, devotional reflection"
            >
              🕊️ Contemplative
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      {isLoading && !result && (
        <div className="loader-container">
          <div className="spinner"></div>
          <div className="loader-text">Consulting the ancient texts with Gemini 4 Argon...</div>
        </div>
      )}

      {result && (
        <div className="results-container">
          <div className="narrative-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
              <h3 className="narrative-title" style={{ margin: 0 }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
                </svg>
                Synthesized Narrative
              </h3>
              {result.model_used && (
                <span style={{ fontSize: '0.75rem', padding: '0.2rem 0.6rem', borderRadius: '12px', background: 'rgba(212, 175, 55, 0.15)', color: '#d4af37', border: '1px solid rgba(212, 175, 55, 0.3)', fontWeight: '500' }}>
                  {result.model_used}
                </span>
              )}
              {result.perspectives && (
                <div className="perspective-badges-row">
                  {result.perspectives.include_midrash && (
                    <span className="perspective-tag active-lens">📜 Midrash</span>
                  )}
                  {result.perspectives.include_patristic && (
                    <span className="perspective-tag active-lens">✝️ Patristic</span>
                  )}
                  {result.perspectives.include_historical && (
                    <span className="perspective-tag active-lens">🏛️ Josephus</span>
                  )}
                  <span className="perspective-tag tone-tag">
                    {result.perspectives.narrative_tone === "scholarly" ? "📖 Scholarly" : result.perspectives.narrative_tone === "meditative" ? "🕊️ Contemplative" : "🎭 Dramatic"}
                  </span>
                </div>
              )}
              {isStreaming && (
                <span className="streaming-badge">
                  <span className="streaming-dot" />
                  Streaming Live
                </span>
              )}
            </div>

            {result.share_id && !isStreaming && (
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
              {result.narrative ? (
                result.narrative.split("\n\n").map((para, i, arr) => (
                  <p key={i}>
                    {para}
                    {isStreaming && i === arr.length - 1 && (
                      <span className="streaming-cursor" aria-hidden="true" />
                    )}
                  </p>
                ))
              ) : isStreaming ? (
                <p className="streaming-placeholder">
                  <span>Synthesizing biblical narrative and ancient traditions...</span>
                  <span className="streaming-cursor" aria-hidden="true" />
                </p>
              ) : null}
            </div>
          </div>

          <aside className="sources-container">
            <h4 className="sources-header">Canonical Scripture ({result.sources.length})</h4>
            {result.sources.map((source, index) => (
              <div key={index} className="source-card">
                <h5 className="source-title">{source.title}</h5>
                <span className="source-id">{source.id}</span>
                <p className="source-text">{source.text}</p>
                {source.hebrew_text && (
                  <details style={{marginTop: '1rem', cursor: 'pointer', fontSize: '0.85rem', color: 'rgba(212, 175, 55, 0.8)'}}>
                    <summary style={{fontWeight: '500'}}>View Original Language (Hebrew)</summary>
                    <p style={{marginTop: '0.5rem', fontFamily: 'serif', direction: 'rtl', textAlign: 'right', fontSize: '1.2rem', lineHeight: '1.6'}}>{source.hebrew_text}</p>
                  </details>
                )}
              </div>
            ))}

            {result.commentaries && result.commentaries.length > 0 && (
              <>
                <h4 className="sources-header source-section-divider">Ancient Traditions & Commentaries ({result.commentaries.length})</h4>
                {result.commentaries.map((comm, index) => (
                  <div key={index} className="source-card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                      <span className={`commentary-badge ${comm.tradition}`}>
                        {comm.tradition === 'midrash' ? '📜 Midrash' : comm.tradition === 'patristic' ? '✝️ Patristic' : '🏛️ Historical'}
                      </span>
                      <span className="source-id" style={{ margin: 0, textTransform: 'none' }}>{comm.reference}</span>
                    </div>
                    <h5 className="source-title" style={{ fontSize: '1.05rem' }}>{comm.title}</h5>
                    <div className="commentary-author">{comm.author} — {comm.work}</div>
                    <p className="source-text" style={{ WebkitLineClamp: 5 }}>{comm.text}</p>
                    {comm.original_language_text && (
                      <details style={{marginTop: '1rem', cursor: 'pointer', fontSize: '0.85rem', color: 'rgba(212, 175, 55, 0.8)'}}>
                        <summary style={{fontWeight: '500'}}>View Original Language</summary>
                        <p style={{marginTop: '0.5rem', fontFamily: 'serif', direction: 'rtl', textAlign: 'right', fontSize: '1.15rem', lineHeight: '1.6'}}>{comm.original_language_text}</p>
                      </details>
                    )}
                  </div>
                ))}
              </>
            )}
          </aside>
        </div>
      )}
    </main>
  );
}



