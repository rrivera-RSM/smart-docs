import type { components } from "./openapi.generated";

export type AnonymizerJob = components["schemas"]["AnonymizerJobResponse"];
export type Capability = components["schemas"]["CapabilitiesResponse"];
export type Finding = components["schemas"]["FindingResponse"];
export type FindingGroup = components["schemas"]["FindingGroupResponse"];
export type TextBlock = components["schemas"]["TextBlockResponse"];
export type CoverageIssue = components["schemas"]["CoverageIssueResponse"];
export type DocumentLocation = components["schemas"]["LocationResponse"];
export type GroupDecision = components["schemas"]["GroupDecision"];
export type ManualFinding = components["schemas"]["ManualFindingRequest"];
export type ConfidenceBand = Finding["confidence_band"];
export type JobStatus = AnonymizerJob["status"];

// The API transports options as a JSON string inside multipart/form-data.
export type AnalysisOptions = {
  profile: "maximum";
  enabled_categories: string[];
  allowlist: string[];
};
