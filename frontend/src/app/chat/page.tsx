"use client";

import { FormEvent, useState } from "react";
import { api, QaResponse } from "@/lib/api";

type ChatMessage = { role: "user" | "assistant"; text: string; sources?: QaResponse["sources"] };

const starterMessages: ChatMessage[] = [
  { role: "assistant", text: "Ask a question about your documents and I will ground the answer in the most relevant passages." },
];

export default function ChatPage() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState(starterMessages);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!question.trim()) {
      return;
    }

    const submittedQuestion = question.trim();
    setQuestion("");
    setError(null);
    setMessages((current) => [...current, { role: "user", text: submittedQuestion }]);

    try {
      setLoading(true);
      const response = await api.askQuestion(submittedQuestion);
      setMessages((current) => [
        ...current,
        { role: "assistant", text: response.answer, sources: response.sources },
      ]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Question failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="page-shell chat-shell">
      <div className="page-header">
        <div>
          <p className="eyebrow">Q&A</p>
          <h1>Chat</h1>
        </div>
      </div>

      <div className="panel chat-panel">
        <div className="chat-log" aria-live="polite">
          {messages.map((message, index) => (
            <div key={`${message.role}-${index}`} className={`chat-bubble ${message.role}`}>
              <span>{message.text}</span>
              {message.sources && message.sources.length > 0 && (
                <div className="source-list">
                  <strong>Sources</strong>
                  {message.sources.map((source) => (
                    <small key={source.chunk_id}>{source.document_filename}: {source.content_preview}</small>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {error && <p className="error-message" role="alert">{error}</p>}

        <form onSubmit={handleSubmit} className="chat-form">
          <label htmlFor="question">Ask about your documents</label>
          <textarea
            id="question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="e.g. What changed in the Q3 revenue forecast?"
            rows={4}
          />
          <button type="submit" className="primary-button" disabled={loading}>
            {loading ? "Thinking..." : "Send"}
          </button>
        </form>
      </div>
    </section>
  );
}
