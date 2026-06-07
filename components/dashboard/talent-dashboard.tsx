"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowDownToLine,
  BarChart3,
  CheckCircle2,
  Clock3,
  FileCheck2,
  Loader2,
  Play,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn, formatPercent, formatScore } from "@/lib/utils";
import type { CandidateRecord, RankingPayload } from "@/types/ranking";

type FilterMode = "all" | "open" | "india" | "clean";

const filters: { id: FilterMode; label: string }[] = [
  { id: "all", label: "All" },
  { id: "open", label: "Open" },
  { id: "india", label: "India" },
  { id: "clean", label: "Low penalty" },
];

const componentLabels: Record<string, string> = {
  technical: "Technical",
  career: "Career",
  role: "Role",
  experience: "Experience",
  location: "Location",
  behavior: "Behavior",
};

export function TalentDashboard({ hosted = false }: { hosted?: boolean }) {
  const [payload, setPayload] = useState<RankingPayload | null>(null);
  const [selectedId, setSelectedId] = useState<string>("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<FilterMode>("all");
  const [isRunning, setIsRunning] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [status, setStatus] = useState("Ready");
  const [validation, setValidation] = useState("");

  async function loadResults() {
    const response = await fetch("/api/results", { cache: "no-store" });
    const data = (await response.json()) as RankingPayload;
    setPayload(data);
    if (!selectedId && data.records?.[0]) {
      setSelectedId(data.records[0].candidate_id);
    }
  }

  useEffect(() => {
    void loadResults();
  }, []);

  const records = payload?.records ?? [];
  const selected = records.find((record) => record.candidate_id === selectedId) ?? records[0];

  const filteredRecords = useMemo(() => {
    const q = query.trim().toLowerCase();
    return records.filter((record) => {
      const searchBlob = [
        record.candidate_id,
        record.profile.current_title,
        record.profile.current_company,
        record.profile.location,
        record.profile.country,
        record.reasoning,
        ...record.top_skills.map((skill) => skill.name),
      ]
        .join(" ")
        .toLowerCase();

      const matchesQuery = !q || searchBlob.includes(q);
      const matchesFilter =
        filter === "all" ||
        (filter === "open" && record.signals.open_to_work) ||
        (filter === "india" && record.profile.country.toLowerCase().includes("india")) ||
        (filter === "clean" && (record.components.penalty ?? 0) <= 0.035);

      return matchesQuery && matchesFilter;
    });
  }, [filter, query, records]);

  const metrics = useMemo(() => {
    const open = records.filter((record) => record.signals.open_to_work).length;
    const india = records.filter((record) => record.profile.country.toLowerCase().includes("india")).length;
    const avgScore = records.reduce((sum, record) => sum + record.score, 0) / Math.max(records.length, 1);
    const avgPenalty = records.reduce((sum, record) => sum + (record.components.penalty ?? 0), 0) / Math.max(records.length, 1);
    return { open, india, avgScore, avgPenalty };
  }, [records]);

  async function runRanking() {
    setIsRunning(true);
    setStatus("Ranking full candidate pool");
    setValidation("");
    try {
      const response = await fetch("/api/run-ranking", { method: "POST" });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        setStatus("Ranking failed");
        setValidation(data.stderr || data.stdout || "Ranker returned an error.");
        return;
      }
      setStatus(`Ranking complete in ${(data.runtime_ms / 1000).toFixed(1)}s`);
      await loadResults();
    } finally {
      setIsRunning(false);
    }
  }

  async function validateSubmission() {
    setIsValidating(true);
    setValidation("");
    try {
      const response = await fetch("/api/validate", { method: "POST" });
      const data = await response.json();
      setValidation(data.stdout || data.stderr || "No validator output.");
      setStatus(response.ok ? "Submission valid" : "Validation failed");
    } finally {
      setIsValidating(false);
    }
  }

  return (
    <main className="min-h-screen">
      <header className="border-b border-border bg-white">
        <div className="mx-auto flex max-w-[1480px] flex-col gap-4 px-4 py-4 md:flex-row md:items-center md:justify-between lg:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-md border border-teal-100 bg-white">
              <img src="/logo.png" alt="Redrob Logo" className="h-full w-full scale-[1.15] object-cover" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-slate-950">Redrob Talent Ranker</h1>
              <p className="text-sm text-muted-foreground">Senior AI Engineer shortlist, generated locally</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {hosted && <Badge variant="muted">Read-only demo</Badge>}
            <StatusPill label={status} running={isRunning || isValidating} />
            <Button variant="outline" onClick={() => void loadResults()} title="Refresh results">
              <RefreshCw className="h-4 w-4" />
              Refresh
            </Button>
            <Button
              variant="outline"
              onClick={() => void validateSubmission()}
              disabled={isValidating || records.length === 0 || hosted}
              title={hosted ? "Validation runs locally only" : "Run the challenge validator"}
            >
              {isValidating ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileCheck2 className="h-4 w-4" />}
              Validate
            </Button>
            <Button asChild variant="outline">
              <a href="/api/submission">
                <ArrowDownToLine className="h-4 w-4" />
                CSV
              </a>
            </Button>
            <Button
              onClick={() => void runRanking()}
              disabled={isRunning || hosted}
              title={hosted ? "Live ranking runs locally only" : "Run the ranker over the full pool"}
            >
              {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              Run Ranking
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1480px] gap-4 px-4 py-5 lg:grid-cols-[290px_minmax(0,1fr)_380px] lg:px-6">
        <aside className="panel order-2 rounded-lg p-4 lg:order-none lg:sticky lg:top-4 lg:h-[calc(100vh-2rem)] lg:overflow-auto">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase text-muted-foreground">Target role</p>
              <h2 className="mt-1 text-base font-semibold text-slate-950">Senior AI Engineer</h2>
            </div>
            <Badge variant="blue">Hybrid</Badge>
          </div>

          <div className="space-y-4 text-sm">
            <Section title="Must prove">
              <SignalLine label="Retrieval" value="Embeddings, vector search, hybrid search" />
              <SignalLine label="Ranking" value="LTR, recommender, search relevance" />
              <SignalLine label="Evaluation" value="NDCG, MRR, A/B tests, offline benchmarks" />
              <SignalLine label="Production" value="Shipped systems, product ownership" />
            </Section>

            <Section title="Scoring stance">
              <SignalLine label="Sweet spot" value="5-9 years, hands-on builder" />
              <SignalLine label="Logistics" value="India, Pune/Noida preferred, relocation useful" />
              <SignalLine label="Signals" value="Active, responsive, open to work" />
              <SignalLine label="Penalties" value="Keyword stuffing, stale profile, side-project-only AI" />
            </Section>

            <Section title="Run summary">
              <SignalLine label="Scanned" value={payload ? payload.summary.scanned_candidates.toLocaleString() : "0"} />
              <SignalLine label="Top K" value={payload ? String(payload.summary.top_k) : "0"} />
              <SignalLine label="Reference" value={payload?.summary.reference_date ?? "2026-06-07"} />
            </Section>
          </div>
        </aside>

        <section className="order-1 min-w-0 space-y-4 lg:order-none">
          <div className="grid gap-3 metric-grid">
            <Metric label="Avg score" value={formatScore(metrics.avgScore)} icon={<BarChart3 className="h-4 w-4" />} />
            <Metric label="Open to work" value={`${metrics.open}/${records.length || 0}`} icon={<Activity className="h-4 w-4" />} />
            <Metric label="India based" value={`${metrics.india}/${records.length || 0}`} icon={<ShieldCheck className="h-4 w-4" />} />
            <Metric label="Avg penalty" value={formatScore(metrics.avgPenalty)} icon={<SlidersHorizontal className="h-4 w-4" />} />
          </div>

          <div className="panel rounded-lg">
            <div className="flex flex-col gap-3 border-b border-border p-3 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <h2 className="text-base font-semibold text-slate-950">Ranked shortlist</h2>
                <p className="text-sm text-muted-foreground">{filteredRecords.length} visible candidates from the generated top 100</p>
              </div>
              <div className="flex flex-col gap-2 md:flex-row md:items-center">
                <div className="relative w-full md:w-72">
                  <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Search candidate, title, skill"
                    className="h-9 w-full rounded-md border border-input bg-white pl-8 pr-3 text-sm outline-none transition focus:ring-2 focus:ring-ring"
                  />
                </div>
                <div className="flex shrink-0 rounded-md border border-border bg-muted p-1">
                  {filters.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => setFilter(item.id)}
                      className={cn(
                        "inline-flex h-7 items-center whitespace-nowrap rounded-sm px-2.5 text-xs font-medium text-muted-foreground transition",
                        filter === item.id && "bg-white text-foreground shadow-sm",
                      )}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="max-h-[660px] overflow-auto">
              <Table>
                <TableHeader className="sticky top-0 z-10 bg-white">
                  <TableRow>
                    <TableHead className="w-16">Rank</TableHead>
                    <TableHead>Candidate</TableHead>
                    <TableHead className="w-28">Score</TableHead>
                    <TableHead className="w-40">Signals</TableHead>
                    <TableHead className="hidden xl:table-cell">Reasoning</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredRecords.map((record) => (
                    <TableRow
                      key={record.candidate_id}
                      data-state={selected?.candidate_id === record.candidate_id ? "selected" : undefined}
                      className="cursor-pointer"
                      onClick={() => setSelectedId(record.candidate_id)}
                    >
                      <TableCell>
                        <span className="font-mono text-sm font-semibold">#{record.rank}</span>
                      </TableCell>
                      <TableCell>
                        <div className="min-w-[260px]">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium text-slate-950">{record.profile.current_title}</span>
                            <Badge variant="muted">{record.candidate_id}</Badge>
                          </div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {record.profile.years_of_experience.toFixed(1)} yrs · {record.profile.location} · {record.profile.current_company}
                          </div>
                          <div className="mt-2 flex flex-wrap gap-1">
                            {record.top_skills.slice(0, 3).map((skill) => (
                              <Badge key={`${record.candidate_id}-${skill.name}`} variant="outline">
                                {skill.name}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="font-mono font-semibold text-slate-950">{formatScore(record.score)}</div>
                        <div className="mt-1 h-1.5 rounded-full bg-muted">
                          <div className="h-1.5 rounded-full bg-teal-700" style={{ width: `${Math.max(record.score * 100, 4)}%` }} />
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {record.signals.open_to_work && <Badge variant="success">Open</Badge>}
                          <Badge variant={record.signals.notice_period_days <= 30 ? "success" : "warning"}>
                            {record.signals.notice_period_days}d
                          </Badge>
                          <Badge variant="blue">{formatPercent(record.signals.recruiter_response_rate)}</Badge>
                        </div>
                      </TableCell>
                      <TableCell className="hidden max-w-[420px] xl:table-cell">
                        <p className="line-clamp-2 text-sm text-muted-foreground">{record.reasoning}</p>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>

          {validation && (
            <div className="panel rounded-lg p-3">
              <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                <CheckCircle2 className="h-4 w-4 text-teal-700" />
                Validator output
              </div>
              <pre className="overflow-auto whitespace-pre-wrap rounded-md bg-slate-950 p-3 text-xs text-slate-100">{validation}</pre>
            </div>
          )}
        </section>

        <aside className="panel order-3 rounded-lg lg:order-none lg:sticky lg:top-4 lg:h-[calc(100vh-2rem)] lg:overflow-auto">
          {selected ? <CandidateDetail record={selected} /> : <EmptyDetail />}
        </aside>
      </div>
    </main>
  );
}

function StatusPill({ label, running }: { label: string; running: boolean }) {
  return (
    <div className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-white px-3 text-sm text-muted-foreground">
      {running ? <Loader2 className="h-4 w-4 animate-spin text-teal-700" /> : <Clock3 className="h-4 w-4 text-amber-600" />}
      <span>{label}</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">{title}</h3>
      <div className="divide-y divide-border rounded-md border border-border">{children}</div>
    </div>
  );
}

function SignalLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 px-3 py-2">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <span className="text-sm text-slate-900">{value}</span>
    </div>
  );
}

function Metric({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="panel rounded-lg p-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase text-muted-foreground">{label}</span>
        <span className="text-teal-700">{icon}</span>
      </div>
      <div className="mt-3 text-2xl font-semibold text-slate-950">{value}</div>
    </div>
  );
}

function CandidateDetail({ record }: { record: CandidateRecord }) {
  const componentEntries = Object.entries(record.components).filter(([key]) => key !== "penalty");
  const penaltyEntries = Object.entries(record.penalties);

  return (
    <div>
      <div className="border-b border-border p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <Badge variant="muted">{record.candidate_id}</Badge>
            <h2 className="mt-2 text-lg font-semibold text-slate-950">{record.profile.current_title}</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {record.profile.current_company} · {record.profile.location}
            </p>
          </div>
          <div className="text-right">
            <div className="font-mono text-xl font-semibold text-slate-950">{formatScore(record.score)}</div>
            <div className="text-xs text-muted-foreground">rank #{record.rank}</div>
          </div>
        </div>
        <p className="mt-4 text-sm leading-6 text-slate-700">{record.reasoning}</p>
      </div>

      <div className="space-y-5 p-4">
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">Score breakdown</h3>
          <div className="space-y-2">
            {componentEntries.map(([key, value]) => (
              <ScoreBar key={key} label={componentLabels[key] ?? key} value={value} />
            ))}
          </div>
        </div>

        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">Technical evidence</h3>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(record.technical_components).map(([key, value]) => (
              <EvidenceChip key={key} label={key.replace("_", " ")} value={value} />
            ))}
          </div>
        </div>

        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">Behavioral signals</h3>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <Fact label="Open" value={record.signals.open_to_work ? "Yes" : "No"} />
            <Fact label="Inactive" value={record.signals.days_inactive === null ? "n/a" : `${record.signals.days_inactive}d`} />
            <Fact label="Response" value={formatPercent(record.signals.recruiter_response_rate)} />
            <Fact label="Notice" value={`${record.signals.notice_period_days}d`} />
            <Fact label="GitHub" value={record.signals.github_activity_score < 0 ? "n/a" : record.signals.github_activity_score.toFixed(0)} />
            <Fact label="Saved" value={String(record.signals.saved_by_recruiters_30d)} />
          </div>
        </div>

        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">Skills</h3>
          <div className="flex flex-wrap gap-1.5">
            {record.top_skills.map((skill) => (
              <Badge key={skill.name} variant="outline">
                {skill.name} · {skill.proficiency}
              </Badge>
            ))}
          </div>
        </div>

        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">Penalties</h3>
          {penaltyEntries.length ? (
            <div className="space-y-2">
              {penaltyEntries.map(([key, value]) => (
                <div key={key} className="flex items-center justify-between rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm">
                  <span className="capitalize text-amber-900">{key.replace("_", " ")}</span>
                  <span className="font-mono text-amber-950">{formatScore(value)}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
              No material penalty.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-slate-700">{label}</span>
        <span className="font-mono text-xs text-muted-foreground">{formatScore(value)}</span>
      </div>
      <div className="h-2 rounded-full bg-muted">
        <div className="h-2 rounded-full bg-teal-700" style={{ width: `${Math.max(value * 100, 3)}%` }} />
      </div>
    </div>
  );
}

function EvidenceChip({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border bg-white px-3 py-2">
      <div className="truncate text-xs font-medium capitalize text-muted-foreground">{label}</div>
      <div className="mt-1 font-mono text-sm font-semibold text-slate-950">{formatScore(value)}</div>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 font-medium text-slate-950">{value}</div>
    </div>
  );
}

function EmptyDetail() {
  return (
    <div className="flex h-full min-h-[360px] items-center justify-center p-6 text-center text-sm text-muted-foreground">
      Generate a ranking to populate candidate evidence.
    </div>
  );
}
