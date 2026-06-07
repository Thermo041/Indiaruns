import { NextResponse } from "next/server";
import rankingResult from "@/outputs/ranking_result.json";

// The ranking output is bundled at build time so it is always available on
// serverless hosts (e.g. Vercel), where reading arbitrary files from the
// working directory at runtime is not reliable. Locally this still reflects
// the latest committed outputs/ranking_result.json.
export async function GET() {
  return NextResponse.json(rankingResult, {
    headers: { "cache-control": "no-store" },
  });
}
