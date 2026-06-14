/** Kanonikus feldolgozási sorrend: megértés → felfedezés → kódolás → indexelés */
export type PipelineCatalogEntry = {
  module: string;
  step: string;
  stage: string;
};

export const PROCESSING_PIPELINE_CATALOG: PipelineCatalogEntry[] = [
  { module: "kb_understanding", step: "EXTRACT_CONTENT", stage: "EXTRACT" },
  { module: "kb_understanding", step: "NORMALIZE_PARTS", stage: "NORMALIZE" },
  { module: "kb_understanding", step: "BUILD_CHUNKS", stage: "CHUNKING" },
  { module: "kb_understanding", step: "VALIDATE_RESULT", stage: "VALIDATION" },
  { module: "kb_discovery", step: "DETECT_LANGUAGE", stage: "LANGUAGE_DETECTION" },
  { module: "kb_discovery", step: "EXTRACT_ENTITIES", stage: "ENTITY_EXTRACTION" },
  { module: "kb_discovery", step: "ENRICH_LOCAL", stage: "LOCAL_KNOWLEDGE_ENRICHMENT" },
  { module: "kb_discovery", step: "EXTRACT_TEMPORAL", stage: "TEMPORAL_EXTRACTION" },
  { module: "kb_discovery", step: "EXTRACT_SPATIAL", stage: "SPATIAL_EXTRACTION" },
  { module: "kb_discovery", step: "EXTRACT_PROCESS", stage: "PROCESS_EXTRACTION" },
  { module: "kb_discovery", step: "BUILD_RELATIONSHIPS", stage: "RELATIONSHIP_BUILD" },
  { module: "kb_discovery", step: "SCORE_KNOWLEDGE", stage: "KNOWLEDGE_SCORING" },
  { module: "kb_discovery", step: "VALIDATE_DISCOVERY", stage: "VALIDATION" },
  { module: "kb_discovery", step: "PIPELINE", stage: "DISCOVERY" },
  { module: "kb_embedding", step: "BUILD_INPUT", stage: "EMBEDDING" },
  { module: "kb_embedding", step: "GENERATE", stage: "EMBEDDING" },
  { module: "kb_embedding", step: "PIPELINE", stage: "EMBEDDING" },
  { module: "kb_indexing", step: "ENSURE_COLLECTION", stage: "INDEXING" },
  { module: "kb_indexing", step: "BUILD_PAYLOAD", stage: "INDEXING" },
  { module: "kb_indexing", step: "UPSERT", stage: "INDEXING" },
  { module: "kb_indexing", step: "VERIFY_QDRANT", stage: "INDEXING" },
  { module: "kb_indexing", step: "READY_FOR_SEARCH", stage: "INDEXING" },
  { module: "kb_indexing", step: "PIPELINE", stage: "INDEXING" },
];

export function catalogKey(module: string, step: string): string {
  return `${module}::${step}`;
}
