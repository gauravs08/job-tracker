# Job Tracker

Automated daily job search for Senior Software Engineer / Cloud Architect / DevOps roles in Espoo/Helsinki, Finland.

## What it does

- Runs daily at **9:00 AM Finland time** via GitHub Actions
- Searches LinkedIn for matching jobs across multiple categories
- Saves daily report as markdown in `jobs/` folder
- Sends email report to configured Gmail address

## Job Categories Tracked

- Senior Software Engineer / Java / Backend
- Cloud Architect / DevOps
- Staff / Principal Engineer
- Kubernetes / Cloud Native

## Setup Email Notifications

To receive daily email reports, add these GitHub repository secrets:

1. Go to **Settings > Secrets and variables > Actions**
2. Add these secrets:
   - `GMAIL_USER`: Your Gmail address (e.g., `sharmagauravs08@gmail.com`)
   - `GMAIL_APP_PASSWORD`: A Gmail App Password (NOT your regular password)

### How to create a Gmail App Password:

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** if not already enabled
3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
4. Select "Mail" and generate a password
5. Use that 16-character password as `GMAIL_APP_PASSWORD`

## Manual Run

You can trigger the job manually from the **Actions** tab > **Daily Job Tracker** > **Run workflow**.

## Reports

Daily reports are saved in the `jobs/` folder with the naming pattern `Jobs-YYYY-MM-DD.md`.
