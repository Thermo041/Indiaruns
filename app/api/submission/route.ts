import { NextResponse } from "next/server";
import rankingResult from "@/outputs/ranking_result.json";

// Build the submission CSV from the bundled ranking output so the download
// works on serverless hosts without reading from the filesystem. Content
// matches outputs/submission.csv (same rows, order, and 4-dp scores).
type Record = { candidate_id: string; rank: number; score: number; reasoning: string };

function csvField(value: string): string {
  return /[",\n\r]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

export async function GET() {
  const records = [...(((rankingResult as { records?: Record[] }).records) ?? [])].sort(
    (a, b) => a.rank - b.rank,
  );

  const lines = ["candidate_id,rank,score,reasoning"];
  for (const r of records) {
    lines.push(
      [
        r.candidate_id,
        String(r.rank),
        Number(r.score).toFixed(4),
        csvField(String(r.reasoning ?? "")),
      ].join(","),
    );
  }
  const csv = lines.join("\r\n") + "\r\n";

  return new NextResponse(csv, {
    headers: {
      "content-type": "text/csv; charset=utf-8",
      "content-disposition": 'attachment; filename="submission.csv"',
      "cache-control": "no-store",
    },
  });
}
