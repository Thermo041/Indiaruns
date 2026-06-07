import { promises as fs } from "fs";
import path from "path";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  const resultPath = path.join(/* turbopackIgnore: true */ process.cwd(), "outputs", "ranking_result.json");
  try {
    const raw = await fs.readFile(resultPath, "utf-8");
    return new NextResponse(raw, {
      headers: {
        "content-type": "application/json; charset=utf-8",
        "cache-control": "no-store",
      },
    });
  } catch {
    return NextResponse.json(
      {
        summary: {
          scanned_candidates: 0,
          top_k: 0,
          reference_date: "2026-06-07",
          max_raw_score: 0,
          min_raw_score: 0,
        },
        records: [],
      },
      { status: 200 },
    );
  }
}
