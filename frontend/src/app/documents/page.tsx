"use client";

import { ChangeEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, DocumentRecord } from "@/lib/api";

export default function DocumentsPage() {
  const fileInput = useRef<HTMLInputElement>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(true);
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
      setError(null);
      const uploaded = await api.uploadDocument(file);
      setDocuments((current) => [uploaded, ...current]);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Upload failed.");
    } finally {
      event.target.value = "";
    }
  }

  return (
    <section className="page-shell">
      <div className="page-header">
        <div>
          <p className="eyebrow">Library</p>
          <h1>Documents</h1>
        </div>
        <input ref={fileInput} type="file" hidden onChange={handleUpload} accept=".pdf,.png,.jpg,.jpeg,.docx" />
        <button type="button" className="primary-button" onClick={() => fileInput.current?.click()}>
          Add document
        </button>
      </div>

      {error && <p className="error-message" role="alert">{error}</p>}

      <div className="panel">
        <table className="document-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Status</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {!loading && documents.length === 0 && (
              <tr><td colSpan={4} className="empty-state">No documents uploaded yet.</td></tr>
            )}
            {documents.map((document) => (
              <tr key={document.id}>
                <td><Link className="document-link" href={`/documents/${document.id}`}>{document.original_filename}</Link></td>
                <td>{document.file_type}</td>
                <td>
                  <span className="status-pill">{document.status}</span>
                </td>
                <td>{new Date(document.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
