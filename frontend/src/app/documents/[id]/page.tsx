"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, DocumentDetail } from "@/lib/api";

export default function DocumentDetailPage() {
  const params = useParams<{ id: string }>();
  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!params.id) return;

    async function loadDocument() {
      try {
        const result = await api.getDocument(params.id);
        setDocument(result);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Unable to load document.");
      } finally {
        setLoading(false);
      }
    }

    void loadDocument();
  }, [params.id]);

  if (loading) {
    return <section className="page-shell"><p className="loading-state">Loading document...</p></section>;
  }

  if (error || !document) {
    return (
      <section className="page-shell">
        <p className="error-message" role="alert">{error ?? "Document not found."}</p>
        <Link className="secondary-button" href="/documents">Back to documents</Link>
      </section>
    );
  }

  return (
    <section className="page-shell">
      <div className="page-header">
        <div>
          <p className="eyebrow">Document detail</p>
          <h1>{document.original_filename}</h1>
          <p className="muted-inline">{document.file_type} · {document.status} · {document.file_size_bytes.toLocaleString()} bytes</p>
        </div>
        <Link className="secondary-button" href="/documents">Back to documents</Link>
      </div>

      {document.processing_error && <p className="error-message" role="alert">{document.processing_error}</p>}

      <div className="detail-grid">
        <section className="panel">
          <div className="panel-header"><h2>AI analysis</h2><span>{document.analysis ? `${Math.round(document.analysis.confidence * 100)}% confidence` : "Pending"}</span></div>
          {document.analysis ? (
            <>
              <p className="detail-summary">{document.analysis.summary}</p>
              <dl className="metadata-list">
                <div><dt>Document type</dt><dd>{document.analysis.document_type}</dd></div>
                <div><dt>Language</dt><dd>{document.analysis.language}</dd></div>
              </dl>
              <div className="entity-list">
                <h3>Entities</h3>
                {document.analysis.entities.length === 0 ? <p className="muted-inline">No entities detected.</p> : document.analysis.entities.map((entity) => <span className="entity-badge" key={`${entity.type}-${entity.name}`}>{entity.name} · {entity.type}</span>)}
              </div>
            </>
          ) : <p className="empty-state">Analysis is not available yet. Processing may still be in progress.</p>}
        </section>

        <section className="panel">
          <div className="panel-header"><h2>Extracted text</h2><span>{document.page_count ? `${document.page_count} pages` : ""}</span></div>
          {document.extracted_text ? <pre className="extracted-text">{document.extracted_text}</pre> : <p className="empty-state">Text extraction is not available yet.</p>}
        </section>
      </div>
    </section>
  );
}
