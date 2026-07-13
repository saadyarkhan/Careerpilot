# CareerPilot — Architecture Reference

(Condensed from IMPLEMENTATION_PLAN.md — consult the full plan doc in the repo root for narrative context.)

## 2. Architecture Diagram

```
                     ┌─────────────────────────┐
                     │      Streamlit UI        │
                     │  (upload, review, chat)  │
                     └────────────┬─────────────┘
                                  │
                     ┌────────────▼─────────────┐
                     │   LangGraph Orchestrator   │
                     │   (stateful graph, checkpoints)
                     └────────────┬─────────────┘
        ┌──────────────┬─────────┼─────────┬──────────────┐
        ▼              ▼         ▼         ▼              ▼
 ┌────────────┐ ┌─────────────┐ ┌───────┐ ┌────────────┐ ┌────────────┐
 │Resume Parser│ │JD Analyzer  │ │Matcher│ │Tailoring    │ │Guardrail    │
 │Agent        │ │Agent        │ │Agent  │ │Agent        │ │Agent        │
 └─────────────┘ └─────────────┘ └───────┘ └────────────┘ └────────────┘
                                  │
                     ┌────────────▼─────────────┐
                     │   Human Approval Gate      │
                     │  (LangGraph interrupt)     │
                     └────────────┬─────────────┘
                                  ▼
                     ┌───────────────────────────┐
                     │  Application Tracker /     │
                     │  SQLite persistence layer  │
                     └───────────────────────────┘
```

## 2b. Provider & Hosting Choices

| Layer | Choice | Notes |
|---|---|---|
| LLM | Google Gemini API (`gemini-2.5-flash` / `flash-lite`) via `langchain-google-genai` | Free tier, no card, ~1,500 req/day. Swappable via `config.yaml` if a paid provider is added later. |
| Embeddings | Gemini Embedding API (same key) | Free tier, 10M TPM — no local model download. |
| Vector index | FAISS (local, on the EC2 instance) | Stores Gemini embedding vectors for similarity search. |
| Structured storage | SQLite via SQLAlchemy | Local file on the EC2 instance's EBS volume. |
| File storage | AWS S3 (private bucket) | Raw resumes + generated tailored documents. Public access blocked; accessed only via the app's IAM role. |
| Compute | AWS EC2 `t3.micro` (free-tier eligible) | Runs the Streamlit app as a systemd service behind Nginx. |
| Access control | AWS IAM role (instance profile) | `s3:GetObject`/`PutObject`/`ListBucket` scoped to only the project bucket. No AWS access keys stored in the app or `.env` on the instance — `boto3` uses the instance role automatically. |

Full step-by-step is in `AWS_DEPLOYMENT.md` at the repo root — always point there for deployment/infra questions rather than improvising AWS CLI commands from scratch, since it already encodes the budget-alarm-first ordering and least-privilege policy JSON.

**Cost discipline:** the AWS account is on a 6-month/$200-credit window (new-account free plan, not the legacy 12-month allowance). Don't recommend RDS, NAT Gateways, larger instance types, or unattached Elastic IPs without flagging the cost. Stopping the EC2 instance when not actively demoing is good practice.

## 3. Agent Responsibilities

| Agent | Input | Output | Notes |
|---|---|---|---|
| Resume Parser Agent | Raw resume (PDF/DOCX) | Structured JSON (skills, roles, dates, bullets, education) | Single source of truth for fact-checking. |
| JD Analyzer Agent | Pasted JD text or URL | Structured JSON (required skills, seniority, keywords) | Treats JD text as untrusted input. |
| Matcher/Scoring Agent | Resume JSON + JD JSON | Fit score (0-100) + gap analysis | Embedding similarity + LLM reasoning pass. |
| Tailoring Agent | Resume JSON + JD JSON + score | Draft tailored resume bullets + cover letter | Must only rephrase/reprioritize real facts. |
| Guardrail/Validator Agent | Tailoring Agent's draft | Pass/fail + flagged issues | Runs automatically before human review. |
| Application Tracker Agent | Approved application | DB write + status | Status: matched → tailored → approved → submitted → response. |
| Orchestrator | — | — | LangGraph StateGraph; conditional edge loops back to Tailoring Agent on guardrail fail; hard interrupt before "submitted". |

## 6. Data Model (SQLite for structured data + S3 for files)

```
resumes(id, uploaded_at, s3_key, parsed_json)
jobs(id, source_url, raw_text, parsed_json, created_at)
matches(id, resume_id, job_id, score, gap_analysis_json, created_at)
applications(id, match_id, tailored_resume_s3_key, cover_letter_s3_key, status, guardrail_report_json, created_at, updated_at)
activity_log(id, application_id, agent_name, action, input_hash, output_summary, passed_guardrail, created_at)
```

`status` enum: `matched → tailored → guardrail_flagged → approved → submitted → interview → rejected → offer`

## 7. UI (Streamlit) Page Map

1. Upload — resume upload + parsed JSON preview
2. Add Job — paste JD/URL + extracted requirements + injection-check status
3. Matches Dashboard — sortable fit scores + gap analysis
4. Review & Tailor — diff view, guardrail flags inline, accept/edit/reject
5. Application Tracker — kanban board by status
6. Activity Log — raw agent trace
7. Settings — rate limits, model selection, PII redaction toggle

## 8. Folder Structure

```
careerpilot/
├── README.md
├── AWS_DEPLOYMENT.md
├── .env.example
├── config.yaml
├── requirements.txt
├── app.py
├── src/
│   ├── graph/
│   │   ├── state.py
│   │   ├── build_graph.py
│   │   └── nodes/
│   │       ├── resume_parser.py
│   │       ├── jd_analyzer.py
│   │       ├── matcher.py
│   │       ├── tailoring.py
│   │       ├── guardrail.py
│   │       └── tracker.py
│   ├── guardrails/
│   │   ├── fact_check.py
│   │   ├── injection_detect.py
│   │   └── rate_limiter.py
│   ├── db/
│   │   ├── models.py
│   │   └── crud.py
│   ├── storage/
│   │   └── s3_client.py
│   ├── parsing/
│   │   ├── resume_parser.py
│   │   └── jd_parser.py
│   └── ui/
│       ├── pages/
│       └── components/
├── tests/
└── .github/workflows/ci.yml
```

## 12. Resume Framing

> CareerPilot — Designed and built a multi-agent job-application assistant (Python, LangGraph, Streamlit) with a guardrail layer for hallucination prevention, human-in-the-loop approval, and prompt-injection resistance; agents handle resume parsing, job matching, and tailored content generation with full audit logging. Deployed on AWS (EC2, S3, IAM) with least-privilege instance roles and budget-alarm cost controls.

Lead with system design (orchestration + guardrails + human-in-the-loop + cloud deployment), not "AI resume tool."
