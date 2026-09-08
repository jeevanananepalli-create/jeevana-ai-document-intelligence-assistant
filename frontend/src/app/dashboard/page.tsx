"use client";

import { ChangeEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, DocumentRecord } from "@/lib/api";

export default function DashboardPage() {
  const fileInput = useRef<HTMLInputElement>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined" || !window.fetch) {
      setLoading(false);
      return;
    }
    void loadDocuments();
  }, []);

  async function loadDocuments() {
    try {
      setError(null);
      const response = await api.listDocuments();
      setDocuments(response.items);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load documents.");
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      setUploading(true);
      setError(null);
      const uploaded = await api.uploadDocument(file);
      setDocuments((current) => [uploaded, ...current]);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Upload failed.");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  const processedCount = documents.filter((document) => document.status === "completed").length;

  return (
    <section className="page-shell">
      <div className="page-header">
        <div>
          <p className="eyebrow">Workspace</p>
          <h1>Dashboard</h1>
        </div>
        <input ref={fileInput} type="file" hidden onChange={handleUpload} accept=".pdf,.png,.jpg,.jpeg,.docx" />
        <button type="button" className="primary-button" onClick={() => fileInput.current?.click()} disabled={uploading}>
          {uploading ? "Uploading..." : "Upload document"}
        </button>
      </div>

      {error && <p className="error-message" role="alert">{error}</p>}

      <div className="stats-grid">
        <div className="stat-card">
          <span>Documents</span>
          <strong>{loading ? "..." : documents.length}</strong>
        </div>
        <div className="stat-card">
          <span>Processed</span>
          <strong>{loading ? "..." : processedCount}</strong>
        </div>
        <div className="stat-card">
          <span>Searches</span>
          <strong>-</strong>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2>Recent uploads</h2>
          <Link href="/documents">Open library</Link>
        </div>

        <div className="document-list">
          {!loading && documents.length === 0 && (
            <p className="empty-state">No documents yet. Upload your first document to begin processing.</p>
          )}
          {documents.slice(0, 5).map((document) => (
            <article key={document.id} className="document-card">
              <div>
                <h3>{document.original_filename}</h3>
                <p>{document.file_type} document, {document.file_size_bytes.toLocaleString()} bytes</p>
              </div>
              <span className="status-pill">{document.status}</span>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
