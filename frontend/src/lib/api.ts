const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_V1_BASE_URL = `${API_BASE_URL}/api/v1`;

export interface HealthResponse {
  status: string;
  service: string;
}

export interface DocumentRecord {
  id: string;
  original_filename: string;
  file_type: string;
  file_size_bytes: number;
  status: string;
  created_at: string;
}

export interface PaginatedDocuments {
  items: DocumentRecord[];
  total: number;
  page: number;
  limit: number;
  has_next: boolean;
}

export interface DocumentEntity {
  name: string;
  type: string;
}

export interface DocumentAnalysis {
  summary: string;
  document_type: string;
  language: string;
  confidence: number;
  entities: DocumentEntity[];
}

export interface DocumentDetail extends DocumentRecord {
  page_count: number | null;
  extracted_text: string | null;
  processing_error: string | null;
  analysis: DocumentAnalysis | null;
  updated_at: string;
}

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  document_filename: string;
  content: string;
  similarity: number;
  chunk_index: number;
  page_number: number | null;
}

export interface QaSource {
  chunk_id: string;
  document_id: string;
  document_filename: string;
  page_number: number | null;
  content_preview: string;
  similarity: number;
}

export interface QaResponse {
  answer: string;
  sources: QaSource[];
  confidence: number;
  model_used: string;
  latency_ms: number;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

async function requestV1<T>(path: string, init?: RequestInit): Promise<T> {
  return request<T>(`${API_V1_BASE_URL}${path}`, init);
}

export const api = {
  getHealth: (): Promise<HealthResponse> => request<HealthResponse>("/health"),

  listDocuments: (): Promise<PaginatedDocuments> =>
    requestV1<PaginatedDocuments>("/documents"),

  getDocument: (documentId: string): Promise<DocumentDetail> =>
    requestV1<DocumentDetail>(`/documents/${documentId}`),

  getDocumentAnalysis: (documentId: string): Promise<DocumentAnalysis> =>
    requestV1<DocumentAnalysis>(`/documents/${documentId}/analysis`),

  uploadDocument: async (file: File): Promise<DocumentRecord> => {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(`${API_V1_BASE_URL}/documents/upload`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.status} ${response.statusText}`);
    }

    return response.json() as Promise<DocumentRecord>;
  },

  askQuestion: (question: string): Promise<QaResponse> =>
    requestV1<QaResponse>("/qa/ask", {
      method: "POST",
      body: JSON.stringify({ question, top_k: 5 }),
    }),

  searchDocuments: (query: string): Promise<{ query: string; results: SearchResult[]; total_results: number }> =>
    requestV1<{ query: string; results: SearchResult[]; total_results: number }>("/search", {
      method: "POST",
      body: JSON.stringify({ query, top_k: 5 }),
    }),
};
