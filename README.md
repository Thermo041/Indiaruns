# Redrob Talent Ranker

Local, free, CPU-only candidate ranking system for the India Runs Data & AI Challenge.

The project ranks the top 100 candidates for the provided Senior AI Engineer JD and produces the required submission CSV:

```text
candidate_id,rank,score,reasoning
```

## Live Demo

- Dashboard (read-only): https://indiaruns.vercel.app/
- Runnable sandbox (Colab, executes the ranker on a sample): see `submission_metadata.yaml` `sandbox_link:https://colab.research.google.com/drive/18Y7XspdreT6rrO2FA8dDqh5AaLK4VUdL?usp=sharing`.

The Vercel dashboard showcases the precomputed top-100 with score breakdowns,
penalties, and per-candidate reasoning. Live ranking/validation run locally only
(no Python or candidate file on the serverless host), so those actions are
disabled in the hosted demo.

## Current Status

- Full `candidates.jsonl` scan completed locally: 100,000 candidates.
- Runtime observed on this Windows machine: about 20.4 seconds with 12 CPU workers.
- Output generated at `outputs/submission.csv`.
- Provided validator result: `Submission is valid.`
- No hosted LLM, paid API, cloud database, GPU, or network call is used during ranking.

## Stack

- Ranking: Python standard library only, including CPU multiprocessing.
- UI: Next.js, React, Tailwind CSS, shadcn-style local components, lucide-react icons.
- Storage: local files under `outputs/`.
- Dataset: provided challenge bundle, kept out of git because it is large.

## Repository Layout

```text
app/                         Next.js app and local API routes
components/                  Dashboard and shadcn-style UI primitives
lib/                         Shared frontend utilities
ranking/rank.py              Official local ranking script
validate_submission.py       Provided format validator (organizer tool)
types/                       TypeScript types for ranking output
outputs/submission.csv       Generated top-100 CSV
outputs/ranking_result.json  Lightweight UI/debug output for top 100
```

## Reproduce The Submission

First, clone this repository to your local machine and navigate into the folder:

```bash
git clone https://github.com/Thermo041/Indiaruns.git
cd Indiaruns
```

For Stage 3 reproduction, place or mount the released candidate file at the repo root:

```bash
./candidates.jsonl
```

Then run:

```bash
python ./ranking/rank.py --candidates ./candidates.jsonl --out ./outputs/submission.csv --json-out ./outputs/ranking_result.json --top-k 100
```

Or use the npm script:

```bash
npm run rank
```

Validate:

```bash
npm run validate
```

Expected validator output:

```text
Submission is valid.
```

## Run The Dashboard

Install dependencies:

```bash
npm install
```

Start the local app:

```bash
npm run dev
```

Open:

```text
http://localhost:3000
```

The dashboard supports:

- Reviewing top-100 candidates.
- Inspecting score breakdowns and penalties.
- Searching/filtering by candidate, title, location, and skills.
- Running the local ranker from the UI.
- Running the challenge validator from the UI.
- Downloading `submission.csv`.

## Ranking Methodology

The ranker is deterministic and streams candidates from JSONL. By default it chooses a safe CPU worker count, scores candidate batches in parallel, keeps per-batch top candidates, and merges them into one global top 100. Single-process and parallel output were checked byte-for-byte on a 5,000-candidate slice.

Scoring combines:

- Technical fit: retrieval, ranking, vector search, evaluation, LLM/ML, Python systems.
- Career evidence: production work-history text, shipped systems, product ownership, long relevant roles.
- Role fit: current title alignment with applied ML, search, ranking, NLP, AI engineering.
- Experience fit: strongest around the JD's 5-9 year senior IC band.
- Location/logistics: India and Pune/Noida-friendly signals, relocation, work mode.
- Behavioral availability: recency, open-to-work, recruiter response, notice period, GitHub activity, interview completion, verification, recruiter attention.
- Penalties: keyword stuffing, side-project-only AI profiles, stale/unresponsive profiles, services-only background, domain mismatch, suspicious skill claims, experience/logistics mismatch.

Reasoning strings are generated from candidate facts already present in the profile. They intentionally mention concrete signals and concerns instead of generic praise.

## Free Sandbox Plan

The official full-dataset ranking is local and network-off. For the required sandbox/demo link, use a free small-sample runner:

- HuggingFace Spaces with a small candidate JSONL sample.
- Streamlit Cloud demo over `sample_candidates.json`.
- Google Colab notebook that runs the same `ranking/rank.py` on a small uploaded sample.
- Docker recipe that mounts `candidates.jsonl` locally.

The sandbox should demonstrate reproducibility on a small sample. The full 100K candidate run remains local and judge-reproducible from the repo.

## Notes

- `requirements.txt` is intentionally empty because `ranking/rank.py` uses only Python standard library modules, so the judged ranking step has no third-party dependencies.
- `package-lock.json` pins the frontend dependency versions installed during this build.
- `npm audit` reports 2 moderate advisories in the Next.js frontend dev dependencies; these affect only the optional dashboard and are never used during ranking.
- Use `--workers 1` for a single-process debug run, or `--workers N` to set an explicit CPU worker count.
