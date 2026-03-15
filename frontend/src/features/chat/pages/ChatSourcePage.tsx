import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../../../api/axiosClient";

type SourcePayload = {
  kb_uuid: string;
  point_id: string;
  title: string;
  content: string;
  created_at?: string | null;
};

export default function ChatSourcePage() {
  const { kbUuid, pointId } = useParams<{ kbUuid: string; pointId: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<SourcePayload | null>(null);

  useEffect(() => {
    let mounted = true;
    const run = async () => {
      if (!kbUuid || !pointId) {
        setError("Hiányzó forrás azonosító.");
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const res = await api.get(`/kb/${kbUuid}/train/points/${pointId}/source`);
        if (!mounted) return;
        setData(res.data as SourcePayload);
      } catch {
        if (!mounted) return;
        setError("A forrás tartalma nem érhető el vagy nincs jogosultság.");
      } finally {
        if (mounted) setLoading(false);
      }
    };
    run();
    return () => {
      mounted = false;
    };
  }, [kbUuid, pointId]);

  return (
    <div className="flex-1 min-h-0 bg-[var(--color-background)] text-[var(--color-foreground)] px-4 py-4">
      <div className="max-w-4xl mx-auto space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold">Forrás tartalom</h1>
          <Link to="/chat" className="text-sm underline">
            Vissza a chathez
          </Link>
        </div>

        {loading && (
          <div className="rounded border border-[var(--color-border)] p-4 text-sm">Betöltés...</div>
        )}

        {!loading && error && (
          <div className="rounded border border-red-300 bg-red-50 text-red-700 p-4 text-sm">
            {error}
          </div>
        )}

        {!loading && !error && data && (
          <div className="rounded border border-[var(--color-border)] p-4 space-y-3">
            <div className="text-sm">
              <div>
                <span className="font-semibold">Cím:</span> {data.title || "(nincs cím)"}
              </div>
              <div>
                <span className="font-semibold">Tudástár:</span> {data.kb_uuid}
              </div>
              <div>
                <span className="font-semibold">Point:</span> {data.point_id}
              </div>
              {data.created_at ? (
                <div>
                  <span className="font-semibold">Létrehozva:</span> {data.created_at}
                </div>
              ) : null}
            </div>
            <div className="border-t border-[var(--color-border)] pt-3">
              <div className="font-semibold mb-2">Tartalom</div>
              <div className="whitespace-pre-wrap break-words text-sm leading-relaxed">
                {data.content || "(üres tartalom)"}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
