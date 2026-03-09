Project: AI Email Sender

Goal:
Build a Python script that reads an Excel file and sends personalized job application emails with an attachment.

Inputs:
Excel columns: Name, Company, Role, Email
Attachment: resume.pdf

Requirements:
• Generate custom email using Ollama (local model).
• Mention company + role naturally.
• Professional tone (not robotic).
• Send via SMTP.
• Add 10 sec delay between emails.
• Save logs.

Tech Stack:
Python, pandas, smtplib, email.message, requests, Ollama API.

Output:
Working script ready to run locally.