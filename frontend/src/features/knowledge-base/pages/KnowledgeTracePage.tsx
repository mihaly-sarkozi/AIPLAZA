import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import Button from "../../../components/ui/Button";
import PageHeader from "../../../components/ui/PageHeader";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import KnowledgeProcessingTrace from "../components/KnowledgeProcessingTrace";
import { getKnowledgeTrace, getLatestKnowledgeTrace, type IngestRunTrace } from "../services";

interface KnowledgeTracePageProps {
  latest?: boolean;
}

export default function KnowledgeTracePage({ latest = false }: KnowledgeTracePageProps) {
  const navigate = useNavigate();
  const { runId } = useParams();
  const [trace, setTrace] = useState<IngestRunTrace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!latest && !runId) {
      setTrace(null);
      setLoading(false);
      setError("No run found.");
      return () => {
        active = false;
      };
    }
    setLoading(true);
    setError(null);
    const load = async () => {
      try {
        const payload = latest ? await getLatestKnowledgeTrace() : await getKnowledgeTrace(runId ?? "");
        if (!active) return;
        setTrace(payload);
      } catch (err) {
        if (!active) return;
        setError(getApiErrorMessage(err) ?? (latest ? "Latest trace nem érhető el." : "Trace nem található."));
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [latest, runId]);

  return (
    <div className="app-page">
      <div className="app-page-container">
        <PageHeader
          eyebrow="Knowledge"
          title={latest ? "Processing Trace - latest" : "Processing Trace"}
          description="Validációs nézet a sentence, mention, claim, claim type és space-time frame lánc gyors ellenőrzésére."
          actions={
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => navigate(-1)}>
                Vissza
              </Button>
              {trace?.run_id ? (
                <Button variant="ghost" onClick={() => navigate(`/knowledge/pipeline-health/${trace.run_id}`)}>
                  Pipeline health
                </Button>
              ) : null}
            </div>
          }
        />

        <KnowledgeProcessingTrace
          trace={trace}
          loading={loading}
          error={error}
          emptyMessage={latest ? "No run found yet." : "No run found."}
        />
      </div>
    </div>
  );
}
