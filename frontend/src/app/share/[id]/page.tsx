"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

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

export default function SharedNarrative() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [isLoading, setIsLoading] = useState(true);
  const [result, setResult] = useState<NarrativeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    const fetchShared = async () => {
      try {
        const res = await fetch(`http://127.0.0.1:8000/shared/${id}`);
        if (!res.ok) {
          const errData = await res.json().catch(() => null);
          throw new Error(errData?.detail || "Narrative not found.");
        }
        const data = await res.json();
        setResult(data);
      } catch (err: any) {
        console.error(err);
        setError(err.message || "Failed to load shared narrative.");
      } finally {
        setIsLoading(false);
      }
    };

    fetchShared();
  }, [id]);

  return (
    <main className="container">
      <header className="header">
        <h1 className="title" onClick={() => router.push("/")} style={{ cursor: "pointer" }}>MTSBE</h1>
        <h2 className="subtitle">Shared Narrative</h2>
      </header>

      {error && (
        <div className="error-message">
          {error}
          <div style={{ marginTop: "1rem" }}>
            <button className="search-button" onClick={() => router.push("/")}>Create a new search</button>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="loader-container">
          <div className="spinner"></div>
          <div className="loader-text">Retrieving ancient scrolls...</div>
        </div>
      )}

      {result && !isLoading && (
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
            </div>
            <button 
              className="search-button" 
              style={{ position: 'absolute', top: '2rem', right: '2rem', padding: '0.5rem 1rem', fontSize: '0.9rem' }}
              onClick={() => router.push("/")}
            >
              Start New Search
            </button>
            <div className="narrative-content">
              {result.narrative.split("\n\n").map((para, i) => (
                <p key={i}>{para}</p>
              ))}
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

