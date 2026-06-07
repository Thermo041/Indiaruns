import { spawn } from "child_process";
import path from "path";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const maxDuration = 300;

function defaultCandidatesPath() {
  return path.join(
    /* turbopackIgnore: true */ process.cwd(),
    "[PUB] India_runs_data_and_ai_challenge",
    "India_runs_data_and_ai_challenge",
    "candidates.jsonl",
  );
}

export async function POST() {
  const python = process.env.PYTHON_BIN || "python";
  const candidates = process.env.CANDIDATES_PATH || defaultCandidatesPath();
  const out = path.join(/* turbopackIgnore: true */ process.cwd(), "outputs", "submission.csv");
  const jsonOut = path.join(/* turbopackIgnore: true */ process.cwd(), "outputs", "ranking_result.json");
  const started = Date.now();

  const result = await new Promise<{ code: number | null; stdout: string; stderr: string }>((resolve) => {
    const child = spawn(
      python,
      [
        path.join(/* turbopackIgnore: true */ process.cwd(), "ranking", "rank.py"),
        "--candidates",
        candidates,
        "--out",
        out,
        "--json-out",
        jsonOut,
        "--top-k",
        "100",
      ],
      {
        cwd: /* turbopackIgnore: true */ process.cwd(),
        windowsHide: true,
      },
    );

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("close", (code) => resolve({ code, stdout, stderr }));
  });

  return NextResponse.json(
    {
      ok: result.code === 0,
      code: result.code,
      runtime_ms: Date.now() - started,
      stdout: result.stdout,
      stderr: result.stderr,
    },
    { status: result.code === 0 ? 200 : 500 },
  );
}
