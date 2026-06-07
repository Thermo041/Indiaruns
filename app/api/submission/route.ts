import { promises as fs } from "fs";
import path from "path";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  const submission = path.join(/* turbopackIgnore: true */ process.cwd(), "outputs", "submission.csv");
  try {
    const csv = await fs.readFile(submission, "utf-8");
    return new NextResponse(csv, {
      headers: {
        "content-type": "text/csv; charset=utf-8",
        "content-disposition": 'attachment; filename="submission.csv"',
        "cache-control": "no-store",
      },
    });
  } catch {
    return NextResponse.json({ ok: false, error: "submission.csv has not been generated yet." }, { status: 404 });
  }
}
