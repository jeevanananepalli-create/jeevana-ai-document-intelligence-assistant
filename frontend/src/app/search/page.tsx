"use client";

import { FormEvent, useState } from "react";
import { api, SearchResult } from "@/lib/api";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!query.trim()) {
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const response = await api.searchDocuments(query.trim());
      setResults(response.results);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Search failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="page-shell">
      <div className="page-header">
        <div>
          <p className="eyebrow">Discovery</p>
          <h1>Search</h1>
        </div>
      </div>

      <div className="panel">
        <form onSubmit={handleSubmit} className="chat-form">
          <label htmlFor="search-query">Search your documents</label>
          <textarea
            id="search-query"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by topic, insight, or document content"
            rows={3}
          />
          <button type="submit" className="primary-button">
            {loading ? "Searching..." : "Search"}
          </button>
        </form>
      </div>

      {error && <p className="error-message" role="alert">{error}</p>}

      <div className="panel">
        <div className="panel-header">
          <h2>Results</h2>
          <span>{results.length} matches</span>
        </div>

        <div className="document-list">
          {!loading && results.length === 0 && (
            <p className="empty-state">Search your documents to see semantically relevant passages.</p>
          )}
          {results.map((result) => (
            <article key={result.chunk_id} className="document-card">
              <div>
                <h3>{result.document_filename}</h3>
                <p className="muted-inline">Chunk {result.chunk_index + 1}{result.page_number ? `, page ${result.page_number}` : ""}</p>
                <p>{result.content}</p>
              </div>
              <span className="status-pill">{result.similarity.toFixed(2)} score</span>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
