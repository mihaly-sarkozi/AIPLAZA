import api from "../../axiosClient";
import type { ParagraphItem, SentenceInterpretationDetail, SentenceItem } from "./types";

export async function listIngestItemSentences(itemId: string): Promise<SentenceItem[]> {
  const res = await api.get(`/knowledge/ingest/items/${itemId}/sentences`);
  return res.data as SentenceItem[];
}

export async function getSentenceInterpretation(sentenceId: string): Promise<SentenceInterpretationDetail> {
  const res = await api.get(`/knowledge/sentences/${sentenceId}/interpretation`);
  return res.data as SentenceInterpretationDetail;
}

export async function listIngestItemParagraphs(itemId: string): Promise<ParagraphItem[]> {
  const res = await api.get(`/knowledge/ingest/items/${itemId}/paragraphs`);
  return res.data as ParagraphItem[];
}
