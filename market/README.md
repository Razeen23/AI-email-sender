# Apply Desk

A separate app from the personal email sender in the parent folder. Nothing there is shared or modified.

Anyone can register, write their own profile, add the countries they want to apply in, and send applications from their own mailbox. Roles and countries are whatever the person types. There is no India or UAE list in the code.

## Run it

From this `market` folder, in two terminals:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload
```

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5174

The personal sender keeps ports 8000 and 5173. Start this app from the `market` folder so Python loads this `backend` package.

## What a person does

1. Register and fill in Profile. A PDF or Word document can fill those fields. Review them, then save.
2. Add target countries (Germany, Remote, UAE, or any other name), with the location line and phone that should appear on applications there.
3. Open Resumes and upload one or more PDF or Word files for each country. One file in that country is the default, and you can change it.
4. Connect a mailbox. Gmail needs an app password, not the normal account password. The password is encrypted and is never sent back to the browser.
5. Add jobs by hand or upload a `.xlsx` or `.csv`. Email is required. Role, company name, job description, skills, country, and referral name are optional. A blank role sends a cold email. After the upload, change the resume on any row, or generate a resume instead.
6. Preview the email. Dry run is the default. A live send waits 10 seconds between messages and stops at 25 sent applications per day. The same company, role, and address is not emailed twice.

Ollama must be running on this machine for previews and tailored resumes. Set `OLLAMA_BASE_URL` and `OLLAMA_MODEL` in `.env`.

## Not in this version

Payments, public hosting, Google login, and job search.
