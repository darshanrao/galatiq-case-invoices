// TypeScript types matching API JSON shape

export type InvoiceStatus =
  | "processing"
  | "approved"
  | "paid"
  | "rejected"
  | "pending_review"
  | "error";

export interface Flag {
  severity: "HARD_FAIL" | "WARNING" | "INFO";
  category: string;
  message: string;
  field?: string;
  details?: string;
}

export interface ItemMatch {
  item_name: string;
  matched_to: string | null;
  match_type: "exact" | "fuzzy" | "unknown";
  similarity_score?: number;
}

export interface ArithmeticResult {
  computed_total: number;
  claimed_total: number;
  matches: boolean;
  discrepancy: number;
}

export interface LineItem {
  item: string;
  quantity: number;
  unit_price: number;
  line_total?: number;
  note?: string;
}

export interface IngestionData {
  status: "success" | "failed";
  vendor?: string;
  amount?: number;
  due_date?: string;
  invoice_number?: string;
  line_items?: LineItem[];
  invoice_date?: string;
  issues?: string[];
}

export interface ValidationData {
  passed: boolean;
  flags: Flag[];
  item_matches: ItemMatch[];
  arithmetic?: ArithmeticResult;
}

export interface ApprovalData {
  decision: "APPROVED" | "REJECTED" | "PENDING_REVIEW";
  risk_score: number;
  reasoning: string;
  prosecution?: string;
  defense?: string;
  source: string;
  llm_recommendation?: string;
}

export interface PaymentData {
  status: "paid" | "rejected";
  vendor?: string;
  amount?: number;
  rejection_reason?: string;
  rejection_stage?: string;
  transaction_id?: string;
  paid_at?: string;
  payment_method?: string;
}

export interface ReviewData {
  id: string;
  invoice_number: string;
  vendor: string;
  amount: number;
  flag_pattern: string;
  risk_score: number;
  recommendation: string;
  flag_explanation: string;
  status: "pending" | "approved" | "rejected";
  created_at: string;
  decided_at?: string;
  decision_reasoning?: string;
}

export interface Invoice {
  id: string;
  file_path?: string;
  original_filename?: string;
  vendor?: string;
  amount?: number;
  due_date?: string;
  status: InvoiceStatus;
  uploaded_at: string;
  completed_at?: string;
  ingestion_data?: IngestionData;
  validation_data?: ValidationData;
  approval_data?: ApprovalData;
  payment_data?: PaymentData;
  review_id?: string;
  review_data?: ReviewData;
}

export interface Stats {
  total: number;
  processing: number;
  approved: number;
  paid: number;
  rejected: number;
  pending_review: number;
  error: number;
}

export interface UploadResponse {
  invoice_id: string;
  status: string;
  filename: string;
}

export interface BatchUploadResponse {
  batch_id: string;
  total_files: number;
  invoice_ids: string[];
  status: string;
}

export interface WsEvent {
  invoice_id: string;
  stage: string;
  data: Record<string, unknown>;
  timestamp: string;
}
