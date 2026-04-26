import { Fragment, useMemo, useState } from "react";
import type { ReactNode } from "react";

import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import { cn } from "../../../utils/cn";
import type { IngestRunTrace } from "../services";
import {
  parsePipelineHealthReport,
  type PipelineCandidateRow,
  type PipelineClaimRow,
  type PipelineEntityRow,
  type PipelineHealthReport,
  type PipelineModuleStatus,
  type PipelineSummaryMetric,
} from "../utils/pipelineHealthReport";

interface PipelineHealthTraceReportProps {
  trace: IngestRunTrace | null | undefined;
  loading?: boolean;
  error?: string | null;
  emptyMessage?: string;
}

const STATUS_TONE: Record<PipelineModuleStatus, string> = {
  OK: "bg-emerald-500/15 text-emerald-700",
  Warning: "bg-amber-500/15 text-amber-700",
  Missing: "bg-slate-500/15 text-slate-700",
  "Not implemented": "bg-zinc-500/15 text-zinc-700",
  "Needs review": "bg-orange-500/15 text-orange-700",
};

function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "good" | "warning" | "danger" | "info" }) {
  const className =
    tone === "good"
      ? "bg-emerald-500/15 text-emerald-700"
      : tone === "warning"
        ? "bg-amber-500/15 text-amber-700"
        : tone === "danger"
          ? "bg-red-500/15 text-red-700"
          : tone === "info"
            ? "bg-sky-500/15 text-sky-700"
            : "bg-[var(--color-border)] text-[var(--color-muted)]";
  return <span className={cn("inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium", className)}>{children}</span>;
}

function StatusBadge({ status }: { status: PipelineModuleStatus }) {
  return <span className={cn("inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold", STATUS_TONE[status])}>{status}</span>;
}

function metricDisplay(metric: PipelineSummaryMetric): string {
  if (metric.missing) return "missing";
  if (metric.value == null) return "-";
  return String(metric.value);
}

function WarningBadges({ claim }: { claim: PipelineClaimRow }) {
  if (claim.warnings.length === 0) return <Badge tone="good">OK</Badge>;
  return (
    <div className="flex flex-wrap gap-1">
      {claim.warnings.map((warning) => (
        <Badge
          key={warning}
          tone={warning === "unknown type" ? "danger" : warning === "relevant unknown space" ? "warning" : "info"}
        >
          {warning}
        </Badge>
      ))}
    </div>
  );
}

function EntityDetails({ entity }: { entity: PipelineEntityRow }) {
  return (
    <div className="grid gap-3 rounded border border-[var(--color-border)] bg-[var(--color-background)] p-3 text-xs">
      <div>
        <div className="mb-1 font-semibold">claims</div>
        {entity.claims.length ? (
          <ul className="list-inside list-disc space-y-1">
            {entity.claims.map((claim, index) => (
              <li key={`${entity.id}-claim-${index}`}>{claim}</li>
            ))}
          </ul>
        ) : (
          <span className="text-[var(--color-muted)]">missing from report</span>
        )}
      </div>
      <div>
        <div className="mb-1 font-semibold">technical memory summary</div>
        <div className="whitespace-pre-wrap">{entity.technicalMemorySummary}</div>
      </div>
      <div>
        <div className="mb-1 font-semibold">search profile canonical text</div>
        <div className="whitespace-pre-wrap">{entity.searchProfileCanonicalText}</div>
      </div>
      <div className="flex flex-wrap gap-1">
        {entity.keywords.length ? entity.keywords.map((keyword) => <Badge key={keyword}>{keyword}</Badge>) : <Badge>keywords missing</Badge>}
      </div>
      <div className="break-all font-mono text-[11px] text-[var(--color-muted)]">
        evidence ids: {entity.evidenceIds.length ? entity.evidenceIds.join(", ") : "missing from report"}
      </div>
    </div>
  );
}

function EntityTable({ rows }: { rows: PipelineEntityRow[] }) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  if (!rows.length) return <div className="text-sm text-[var(--color-muted)]">missing from report</div>;
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full border-separate border-spacing-0 text-xs">
        <thead>
          <tr className="text-left text-[var(--color-muted)]">
            {["name", "type", "claims", "coherence", "time", "space", "status", "evidence", ""].map((head) => (
              <th key={head} className="border-b border-[var(--color-border)] px-2 py-2 font-medium">
                {head}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((entity) => (
            <Fragment key={entity.id}>
              <tr className="align-top">
                <td className="border-b border-[var(--color-border)] px-2 py-2 font-medium">{entity.name}</td>
                <td className="border-b border-[var(--color-border)] px-2 py-2">{entity.type}</td>
                <td className="border-b border-[var(--color-border)] px-2 py-2">{entity.claimsCount}</td>
                <td className="border-b border-[var(--color-border)] px-2 py-2">{entity.coherence == null ? "-" : entity.coherence.toFixed(2)}</td>
                <td className="border-b border-[var(--color-border)] px-2 py-2">{entity.timeMode}</td>
                <td className="border-b border-[var(--color-border)] px-2 py-2">{entity.spaceMode}</td>
                <td className="border-b border-[var(--color-border)] px-2 py-2">
                  <StatusBadge status={entity.status} />
                </td>
                <td className="border-b border-[var(--color-border)] px-2 py-2">{entity.evidenceCount}</td>
                <td className="border-b border-[var(--color-border)] px-2 py-2 text-right">
                  <Button size="sm" variant="ghost" onClick={() => setExpanded((current) => ({ ...current, [entity.id]: !current[entity.id] }))}>
                    {expanded[entity.id] ? "Hide" : "Open"}
                  </Button>
                </td>
              </tr>
              {expanded[entity.id] ? (
                <tr>
                  <td colSpan={9} className="px-2 py-2">
                    <EntityDetails entity={entity} />
                  </td>
                </tr>
              ) : null}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ClaimTable({ rows }: { rows: PipelineClaimRow[] }) {
  if (!rows.length) return <div className="text-sm text-[var(--color-muted)]">missing from report</div>;
  return (
    <div className="max-h-[520px] overflow-auto">
      <table className="min-w-full border-separate border-spacing-0 text-xs">
        <thead className="sticky top-0 bg-[var(--color-surface)]">
          <tr className="text-left text-[var(--color-muted)]">
            {["sentence", "subject", "predicate", "object", "type", "group", "confidence", "time", "space", "subject_source", "warnings"].map((head) => (
              <th key={head} className="border-b border-[var(--color-border)] px-2 py-2 font-medium">
                {head}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((claim) => (
            <tr key={claim.id} className="align-top">
              <td className="max-w-[360px] border-b border-[var(--color-border)] px-2 py-2">{claim.sentence}</td>
              <td className="border-b border-[var(--color-border)] px-2 py-2">{claim.subject}</td>
              <td className="border-b border-[var(--color-border)] px-2 py-2">{claim.predicate}</td>
              <td className="border-b border-[var(--color-border)] px-2 py-2">{claim.object}</td>
              <td className="border-b border-[var(--color-border)] px-2 py-2">
                <Badge tone={claim.type === "unknown" || claim.type === "other" ? "danger" : "neutral"}>{claim.type}</Badge>
              </td>
              <td className="border-b border-[var(--color-border)] px-2 py-2">{claim.group}</td>
              <td className="border-b border-[var(--color-border)] px-2 py-2">
                <Badge tone={claim.confidence < 0.6 ? "danger" : claim.confidence < 0.75 ? "warning" : "good"}>{claim.confidence.toFixed(2)}</Badge>
              </td>
              <td className="border-b border-[var(--color-border)] px-2 py-2">{claim.timeMode}</td>
              <td className="border-b border-[var(--color-border)] px-2 py-2">{claim.spaceMode}</td>
              <td className="border-b border-[var(--color-border)] px-2 py-2">
                <Badge tone={claim.subjectSource === "carryover" ? "warning" : "neutral"}>{claim.subjectSource}</Badge>
              </td>
              <td className="border-b border-[var(--color-border)] px-2 py-2">
                <WarningBadges claim={claim} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CandidateTable({ rows }: { rows: PipelineCandidateRow[] }) {
  if (!rows.length) return <div className="text-sm text-[var(--color-muted)]">missing from report</div>;
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full border-separate border-spacing-0 text-xs">
        <thead>
          <tr className="text-left text-[var(--color-muted)]">
            {["candidate_name", "candidate_type", "score", "band", "reasons", "component scores"].map((head) => (
              <th key={head} className="border-b border-[var(--color-border)] px-2 py-2 font-medium">
                {head}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.source}-${row.id}`} className="align-top">
              <td className="border-b border-[var(--color-border)] px-2 py-2 font-medium">{row.candidateName}</td>
              <td className="border-b border-[var(--color-border)] px-2 py-2">{row.candidateType}</td>
              <td className="border-b border-[var(--color-border)] px-2 py-2">{row.score.toFixed(2)}</td>
              <td className="border-b border-[var(--color-border)] px-2 py-2">
                <Badge tone={row.band === "high" ? "good" : row.band === "medium" ? "warning" : "danger"}>{row.band}</Badge>
              </td>
              <td className="max-w-[360px] border-b border-[var(--color-border)] px-2 py-2">{row.reasons.join(", ") || "-"}</td>
              <td className="border-b border-[var(--color-border)] px-2 py-2 font-mono">
                {Object.keys(row.componentScores).length
                  ? Object.entries(row.componentScores)
                      .map(([key, value]) => `${key}:${Number(value).toFixed(2)}`)
                      .join(" ")
                  : "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ImportPanel({ onParsed }: { onParsed: (report: PipelineHealthReport | null) => void }) {
  const [text, setText] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);
  return (
    <details className="app-surface p-4">
      <summary className="cursor-pointer text-sm font-semibold">Paste JSON / txt trace report</summary>
      <div className="mt-3 grid gap-3">
        <textarea
          className="min-h-40 rounded border border-[var(--color-border)] bg-transparent p-3 font-mono text-xs"
          placeholder="Paste raw JSON or saved AI trace report txt..."
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
        {parseError ? <Alert tone="error">{parseError}</Alert> : null}
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => {
              try {
                onParsed(parsePipelineHealthReport(text));
                setParseError(null);
              } catch (err) {
                setParseError(err instanceof Error ? err.message : "Report parse failed.");
              }
            }}
          >
            Parse pasted report
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => {
              setText("");
              setParseError(null);
              onParsed(null);
            }}
          >
            Use API trace
          </Button>
        </div>
      </div>
    </details>
  );
}

export default function PipelineHealthTraceReport({ trace, loading = false, error, emptyMessage = "No trace found." }: PipelineHealthTraceReportProps) {
  const [manualReport, setManualReport] = useState<PipelineHealthReport | null>(null);
  const apiReport = useMemo(() => (trace ? parsePipelineHealthReport(trace) : null), [trace]);
  const report = manualReport ?? apiReport;

  if (loading) return <Alert tone="info">Trace betöltése folyamatban...</Alert>;
  if (error && !manualReport) return <Alert tone="error">{error}</Alert>;
  if (!report) {
    return (
      <section className="space-y-4">
        <Alert tone="info">{emptyMessage}</Alert>
        <ImportPanel onParsed={setManualReport} />
      </section>
    );
  }

  const combinedCandidates = [...report.candidate_selection, ...report.similarity_analysis];
  const combinedEntities = [...report.local_entities, ...report.technical_entities];
  const lowSimilarityCount = report.similarity_analysis.filter((row) => row.band === "low").length;

  return (
    <section className="space-y-4">
      <div className="app-surface p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Pipeline Health / Trace Report</h2>
            <div className="mt-1 text-xs text-[var(--color-muted)]">
              run={report.runId} · source={report.sourceName} · status={report.status} · input={report.source}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {report.nextActions.slice(0, 4).map((action) => (
              <Badge key={action} tone="warning">
                {action}
              </Badge>
            ))}
          </div>
        </div>
      </div>

      <ImportPanel onParsed={setManualReport} />

      <div className="grid gap-2 md:grid-cols-4 xl:grid-cols-8">
        {report.summary.map((metric) => (
          <div key={metric.key} className="rounded border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
            <div className="truncate font-mono text-[11px] text-[var(--color-muted)]">{metric.label}</div>
            <div className={cn("mt-1 text-xl font-semibold", metric.missing && "text-amber-700")}>{metricDisplay(metric)}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="app-surface p-4">
          <h3 className="text-sm font-semibold">Module status</h3>
          <div className="mt-3 grid gap-2">
            {report.modules.map((module) => (
              <div key={module.name} className="grid grid-cols-[minmax(180px,1fr)_120px_minmax(160px,1fr)] items-center gap-2 border-b border-[var(--color-border)] py-2 text-xs">
                <div className="font-medium">{module.name}</div>
                <StatusBadge status={module.status} />
                <div className="text-[var(--color-muted)]">{module.detail}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="app-surface p-4">
          <h3 className="text-sm font-semibold">Errors / weak signals</h3>
          <div className="mt-3 grid gap-2">
            {report.issues.map((issue) => (
              <div key={issue.key} className="flex items-center justify-between gap-3 border-b border-[var(--color-border)] py-2 text-xs">
                <div>
                  <div className="font-medium">{issue.label}</div>
                  <div className="text-[var(--color-muted)]">{issue.detail}</div>
                </div>
                <Badge tone={issue.count > 0 ? issue.severity : "good"}>{issue.count}</Badge>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="app-surface p-4">
        <h3 className="text-sm font-semibold">Next actions</h3>
        <div className="mt-3 flex flex-wrap gap-2">
          {report.nextActions.map((action) => (
            <Badge key={action} tone="warning">
              {action}
            </Badge>
          ))}
        </div>
      </div>

      <details open className="app-surface p-4">
        <summary className="cursor-pointer text-sm font-semibold">Entity list</summary>
        <div className="mt-3">
          <EntityTable rows={combinedEntities} />
        </div>
      </details>

      <details open className="app-surface p-4">
        <summary className="cursor-pointer text-sm font-semibold">Claim list</summary>
        <div className="mt-3">
          <ClaimTable rows={report.claims} />
        </div>
      </details>

      <details open className="app-surface p-4">
        <summary className="cursor-pointer text-sm font-semibold">Candidate / Similarity view</summary>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          {report.quality.highSimilarityCount === 0 ? <Badge tone="warning">high similarity nincs</Badge> : null}
          {lowSimilarityCount > report.similarity_analysis.length / 2 && report.similarity_analysis.length > 0 ? (
            <Badge tone="warning">sok low similarity</Badge>
          ) : null}
          {report.quality.duplicateCandidateCount > 0 ? <Badge tone="warning">ismétlődő candidate ugyanarra az entityre</Badge> : null}
        </div>
        <div className="mt-3">
          <CandidateTable rows={combinedCandidates} />
        </div>
      </details>

      {report.missingFields.length ? (
        <div className="font-mono text-xs text-[var(--color-muted)]">missing from report: {report.missingFields.join(", ")}</div>
      ) : null}
    </section>
  );
}
