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
