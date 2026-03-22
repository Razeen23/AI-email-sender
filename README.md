# AI Email Sender

Python script that reads an Excel file (Indian or UAE companies), selects the right resume PDF by role, generates personalized job-application email bodies with Ollama, and sends them via SMTP with a 10-second delay between emails.

## Setup

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Ollama**

   - Install [Ollama](https://ollama.com) and run it locally.
   - Pull a model, e.g. `ollama pull llama3.2`.

3. **SMTP**

   - Set SMTP credentials (e.g. Gmail: use an [App Password](https://support.google.com/accounts/answer/185833), not your normal password).

4. **Environment**

   - Copy `.env.example` to `.env` and fill in your values:

   ```bash
   cp .env.example .env
   ```

   Required: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL`.  
   Optional: `RESUMES_BASE` (default `resumes`), `PROFILE_FILE` (default `profile.txt`), `OLLAMA_BASE_URL`, `OLLAMA_MODEL`.

## Usage

- **Indian companies** (uses `resumes/INR`, role-based PDF):

  ```bash
  python send_emails.py inr_companies_test.xlsx
  ```

- **INR job listings (last 24 hours)** (uses `resumes/INR`, tailored using Job Description + Key Skills + Why Match):

  ```bash
  python send_emails2.py INR_Excel/job_listings_last24hours.xlsx --dry-run
  ```

- **UAE companies** (uses `resumes/UAE`, role-based PDF):

  ```bash
  python send_emails.py uae_companies_test.xlsx
  ```

- **Force region** if the filename does not contain `inr` or `uae`:

  ```bash
  python send_emails.py my_sheet.xlsx --region uae
  ```

- **Dry run** (generate bodies and log only; no emails sent):

  ```bash
  python send_emails.py inr_companies_test.xlsx --dry-run
  ```

## Profile (optional)

Put your basic info in `profile.txt` (or set `PROFILE_FILE` in `.env`). Include your **email**, **name**, **phone**, **work experience**, and **projects**. Lines starting with `#` are ignored. The script uses this to personalize each email; the AI picks what to include based on the job role (e.g. frontend role → relevant frontend experience or projects).

## Excel format

Columns (names normalized): `company name`, `role`, `HR email`, `referal name` (optional), `job description` (optional). Rows with missing or invalid HR email are skipped. If **job description** is provided, the email is tailored to the JD using only experience/skills from your profile that actually match—the script will not claim skills or experience you don’t have.

## Resume selection

- **INR:** `resumes/INR/` — e.g. `front-end-inr`, `full-stack-inr`, `react-js-inr`. Unmatched roles use `full-stack-inr`.
- **UAE:** `resumes/UAE/` — e.g. `front-end-uae`, `full-stack-uae`, `react-js-uae`, `gen-ai-uae`. Unmatched roles use `full-stack-uae`.

Role is matched (case-insensitive) to keywords: frontend, full stack, react, gen ai (UAE only). The first PDF in the chosen folder is attached.

## Logs

Logs are written to `logs/email_sender_run_YYYYMMDD_HHMMSS.log` (or `email_sender_dryrun_...` for `--dry-run`). Console output is INFO level.

---

## Generate resume (generate_resume.py)

Reads the same Excel file format as `send_emails.py`, loops over rows, and generates one tailored resume PDF per row (company + role + job description). **After each new PDF, sends one email with that PDF attached** using `send_generated_resume_email.py` (this flow does not use `send_emails.py`). Rows without a job description are skipped; rows whose PDF already exists are skipped. Output is saved under `resumes/{region}/generated/`.

### Setup for generate_resume.py

1. **Dependencies** — Same as above: `pip install -r requirements.txt` (pandas, openpyxl for Excel; markdown, weasyprint for Markdown → PDF). If WeasyPrint is not installed, only the Markdown file is saved (no PDF).
2. **Ollama** — Must be running locally (e.g. `ollama serve`); same model as in `.env` (e.g. `OLLAMA_MODEL=llama3.2`).
3. **Environment** — Same `.env` as the email sender. For **sending** emails after each generated PDF, set SMTP vars: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL`. Optional: `RESUMES_BASE`, `PROFILE_FILE`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`.
4. **Profile** — `profile.txt` (or `PROFILE_FILE`) must exist; resumes are generated only from this content.

### Usage

```bash
python generate_resume.py inr_companies_test.xlsx --region inr
```

- **excel_path** — Path to Excel file. Required columns (same as send_emails): company name, role, HR email, job description. Rows without job description are skipped; rows without valid HR email skip sending but can still generate a PDF.
- **--region** — `inr` or `uae`. Optional; if omitted, region is inferred from the filename (e.g. `inr` in `inr_companies_test.xlsx`).
- **--dry-run** — Generate PDFs only; do not send emails (useful if SMTP is not set or you only want to build resumes).

### Example run

```text
$ python generate_resume.py inr_companies_test.xlsx --region inr
Loaded 5 rows from inr_companies_test.xlsx (region=INR).
[1/5] Skipped Acme Corp / Frontend (no job description).
[2/5] Generating resume for Zoho / Frontend Developer...
[2/5] Saved PDF: resumes/INR/generated/zoho-frontend-developer.pdf
Sent to hr@zoho.com (Company: Zoho, Role: Frontend Developer)
Waiting 10 seconds before next email...
[3/5] Skipped Beta Inc / Full Stack (PDF already exists).
...
Done. Generated: 2, sent: 2, skipped (no JD): 2, skipped (exists): 1, skipped (no email): 0, failed: 0.
```

With `--dry-run`: PDFs are created but no emails are sent; the summary shows `sent: 0`.

Output paths:

- `resumes/INR/generated/{company-slug}-{role-slug}.pdf` (and `.md`)
- `resumes/UAE/generated/{company-slug}-{role-slug}.pdf` (and `.md`)

Example: `resumes/INR/generated/zoho-frontend-developer.pdf`.

The module `send_generated_resume_email.py` is used by `generate_resume.py` to send each email with the new PDF attached; it is standalone (does not use `send_emails.py`).

### Using generated resumes in send_emails

`send_emails.py` (CLI and Email preview API) prefers a company-specific generated PDF when it exists under `resumes/{region}/generated/{company-slug}-{role-slug}.pdf`, and otherwise uses the role-based folder (e.g. `full-stack-inr`). No extra configuration needed.
