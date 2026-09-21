export type Finding = {
  id: string;
  entity_type: string;
  label: string;
  value: string;
  replacement: string;
  location: string;
  start: number;
  end: number;
  context: string;
  confidence: number;
};

export type AnonymizerAnalysis = {
  job_id: string;
  filename: string;
  expires_in_minutes: number;
  findings: Finding[];
  summary: Record<string, number>;
  limitations: string[];
};

export type AnonymizationResult = {
  job_id: string;
  applied_count: number;
  remaining_count: number;
  download_url: string;
  filename: string;
};

export type TemplateIssue = {
  location: string;
  variable: string;
  paragraph_preview: string;
  run_texts: string[];
};

export type GeneratorAnalysis = {
  job_id: string;
  filename: string;
  expires_in_minutes: number;
  ready: boolean;
  document_format: "docx" | "pdf" | "pptx";
  variables: string[];
  issues: TemplateIssue[];
  merge_count?: number;
};

export type GenerationResult = {
  job_id: string;
  filename: string;
  download_url: string;
};
