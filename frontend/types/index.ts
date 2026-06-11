export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  tenant_id: string | null;
  is_active: boolean;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

export interface Document {
  id: string;
  original_filename: string;
  status: string;
  classification: string;
  uploaded_by_id: string;
  tenant_id: string;
  created_at: string;
  pii_findings_count?: number | null;
}

export interface SourceReference {
  document_id: string;
  filename: string;
  page_number: number | null;
  chunk_index: number;
  score: number;
  text_preview: string;
}

export interface RAGQueryResponse {
  answer: string;
  sources: SourceReference[];
  warning?: string | null;
}

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  retrieved_doc_ids: string | null;
  latency_ms: number | null;
  created_at: string;
}

export interface AuditEvent {
  id: string;
  event_type: string;
  entity_type: string | null;
  entity_id: string | null;
  user_id: string | null;
  tenant_id: string | null;
  metadata_json: string | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface PiiFinding {
  id: string;
  document_id: string;
  chunk_id: string;
  pii_type: string;
  matched_text_preview: string;
  created_at: string;
}

export interface EvalRun {
  id: string;
  run_name: string;
  status: string;
  total_questions: number;
  completed_questions: number;
  faithfulness: number | null;
  answer_relevancy: number | null;
  context_recall: number | null;
  context_precision: number | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface InviteResponse {
  invite_token: string;
  email: string;
  role: string;
  expires_at: string;
}
