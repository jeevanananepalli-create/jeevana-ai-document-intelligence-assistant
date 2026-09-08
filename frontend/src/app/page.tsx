import Link from "next/link";

export default function HomePage() {
  return (
    <section className="hero-panel">
      <div className="eyebrow">AI document intelligence</div>
      <h1>AI Document Intelligence Assistant</h1>
      <p className="lead">
        Upload documents, extract key information, search semantically, and ask
        questions without leaving the dashboard.
      </p>

      <div className="cta-row">
        <Link href="/dashboard" className="primary-button" aria-label="Open dashboard">
          Open dashboard
        </Link>
        <Link href="/documents" className="secondary-button" aria-label="Document library">
          Document library
        </Link>
      </div>

      <div className="feature-grid">
        <div className="feature-card">
          <h2>Upload</h2>
          <p>Drop PDFs, images, and DOCX files for automated processing.</p>
        </div>
        <div className="feature-card">
          <h2>Analyze</h2>
          <p>Review summaries, classifications, and extracted entities.</p>
        </div>
        <div className="feature-card">
          <h2>Ask</h2>
          <p>Query your documents with grounded answers and source citations.</p>
        </div>
      </div>
    </section>
  );
}
