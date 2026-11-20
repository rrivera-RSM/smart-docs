export type LineStatus = "proposed" | "accepted" | "pending";

export type InvoiceLine = {
  id: string;
  user: string;
  project_reference: string;
  service: string;
  quantity: number;
  unit_price: number;
  amount: number;
  confidence: number;
  status: LineStatus;
  comment: string;
};

export type InvoiceLineUpdate = Partial<
  Pick<
    InvoiceLine,
    | "user"
    | "project_reference"
    | "service"
    | "quantity"
    | "unit_price"
    | "amount"
    | "status"
    | "comment"
  >
>;

export type InvoiceAnalysis = {
  job_id: string;
  provider: string;
  invoice_number: string;
  invoice_date: string;
  customer_code: string;
  customer_name: string;
  taxable_base: number;
  tax_rate: number;
  tax_amount: number;
  invoice_total: number;
  lines: InvoiceLine[];
  warnings: string[];
  reconciliation: {
    line_total: number;
    taxable_base: number;
    absolute_difference: number;
    percentage_difference: number;
    tolerance_percentage: number;
    matches: boolean;
  };
};

export type ProviderSummary = {
  id: string;
  name: string;
  description: string;
  mode: "grouped_detail" | "flat";
  built_in: boolean;
  detection_terms: string[];
};

export type ProviderTestResult = {
  detection_matches: boolean;
  analysis: InvoiceAnalysis;
};

export type ObservedAccessUser = {
  email: string;
  name: string;
  first_seen_at: string;
  last_seen_at: string;
  status: "allowed";
};

export type AccessOverview = {
  policy: {
    mode: "tenant";
    auth_enabled: boolean;
    tenant_configured: boolean;
    additional_filtering: false;
    allowed: string;
    denied: string;
  };
  users: ObservedAccessUser[];
};

