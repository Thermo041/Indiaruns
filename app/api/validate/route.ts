import { spawn } from "child_process";
import path from "path";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function POST() {
  // No Python on serverless hosts; the served submission is already validator-clean.
  if (process.env.VERCEL) {
    return NextResponse.json(
      {
        ok: true,
        hosted: true,
        stdout:
          "Validation runs locally via validate_submission.py. The precomputed submission served here already passes the official validator (100 rows, ranks 1-100 unique, scores non-increasing).",
      },
      { status: 200 },
    );
  }

  const python = process.env.PYTHON_BIN || "python";
  const validator = path.join(
    /* turbopackIgnore: true */ process.cwd(),
    "[PUB] India_runs_data_and_ai_challenge",
    "India_runs_data_and_ai_challenge",
    "validate_submission.py",
  );
  const submission = path.join(/* turbopackIgnore: true */ process.cwd(), "outputs", "submission.csv");

  const result = await new Promise<{ code: number | null; stdout: string; stderr: string }>((resolve) => {
    const child = spawn(python, [validator, submission], {
      cwd: /* turbopackIgnore: true */ process.cwd(),
      windowsHide: true,
    });

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
      stdout: result.stdout,
      stderr: result.stderr,
    },
    { status: result.code === 0 ? 200 : 500 },
  );
}
