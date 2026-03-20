"""
Job Tracker - Scrapes LinkedIn job search pages and compiles daily report.
Sends email via Gmail SMTP and commits results to repo.
"""

import os
import json
import smtplib
import urllib.request
import urllib.parse
import re
import time
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

TODAY = datetime.now().strftime("%Y-%m-%d")

# Job search configurations matching Gaurav's profile
SEARCHES = [
    {
        "category": "Senior Software Engineer / Java / Backend",
        "queries": [
            ("Java Developer jobs Finland", "https://fi.linkedin.com/jobs/java-developer-jobs"),
            ("Spring Boot jobs Finland", "https://fi.linkedin.com/jobs/spring-boot-jobs-finland"),
            ("Senior Software Engineer Helsinki", "https://www.linkedin.com/jobs/senior-software-engineer-jobs-helsinki"),
        ]
    },
    {
        "category": "Cloud Architect / DevOps",
        "queries": [
            ("Cloud Architect jobs Finland", "https://fi.linkedin.com/jobs/cloud-architect-jobs"),
            ("AWS Cloud Architect jobs Finland", "https://fi.linkedin.com/jobs/aws-cloud-architect-jobs"),
            ("DevOps jobs Finland", "https://fi.linkedin.com/jobs/devops-jobs"),
            ("DevOps Cloud Engineer Helsinki", "https://fi.linkedin.com/jobs/devops-cloud-engineer-jobs-helsinki"),
        ]
    },
    {
        "category": "Staff / Principal Engineer",
        "queries": [
            ("Staff Engineer jobs Finland", "https://fi.linkedin.com/jobs/staff-engineer-jobs"),
            ("Principal Software Engineer Finland", "https://fi.linkedin.com/jobs/principal-software-engineer-jobs"),
            ("Software Architect jobs Finland", "https://fi.linkedin.com/jobs/software-architect-jobs"),
        ]
    },
    {
        "category": "Kubernetes / Cloud Native",
        "queries": [
            ("Kubernetes jobs Finland", "https://fi.linkedin.com/jobs/kubernetes-jobs"),
            ("Cloud Engineer jobs Finland", "https://fi.linkedin.com/jobs/cloud-engineer-jobs"),
            ("Cloud Developer jobs Finland", "https://fi.linkedin.com/jobs/cloud-developer-jobs"),
        ]
    },
]

# Target companies known to be stable and hiring in Espoo/Helsinki
TARGET_COMPANIES = [
    "Nokia", "KONE", "Siemens", "Honeywell", "Nordea", "TietoEVRY", "Tietoevry",
    "Trimble", "GE Healthcare", "Ericsson", "Ritchie Bros", "ASSA ABLOY",
    "Konecranes", "Gofore", "Reaktor", "Siili", "Vincit", "Aiven", "Oura",
    "ICEYE", "Wolt", "DoorDash", "AlphaSense", "IQM", "Fortum", "Neste",
    "Supercell", "Rovio", "Unity", "Microsoft", "Google", "Wipro", "Nordcloud",
    "Futurice", "Codento", "Eficode", "Solita", "CGI", "Accenture", "Zalando",
    "Resurs Bank", "OP Financial", "Sampo", "Danske Bank", "Huawei",
]


def fetch_page(url):
    """Fetch a web page and return its text content. Includes delay to avoid rate limiting."""
    # Random delay between 3-7 seconds to avoid LinkedIn 429 rate limiting
    delay = random.uniform(3, 7)
    time.sleep(delay)
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,fi;q=0.8",
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print(f"  [WARN] Rate limited on {url}, retrying after 15s...")
            time.sleep(15)
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=20) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except Exception as e2:
                print(f"  [WARN] Retry also failed for {url}: {e2}")
                return ""
        else:
            print(f"  [WARN] Failed to fetch {url}: {e}")
            return ""
    except Exception as e:
        print(f"  [WARN] Failed to fetch {url}: {e}")
        return ""


def extract_job_count(html):
    """Try to extract job count from LinkedIn search page."""
    patterns = [
        r'(\d[\d,]+)\s*(?:jobs?|results?)',
        r'"totalResults"\s*:\s*(\d+)',
        r'of\s+(\d[\d,]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1).replace(",", "")
    return "N/A"


def extract_jobs_from_html(html):
    """Extract job titles and company names from LinkedIn HTML."""
    jobs = []
    # Try to find job cards in the HTML
    title_pattern = r'<(?:h3|span)[^>]*class="[^"]*(?:job-title|base-search-card__title)[^"]*"[^>]*>\s*(.*?)\s*</(?:h3|span)>'
    company_pattern = r'<(?:h4|a)[^>]*class="[^"]*(?:company-name|base-search-card__subtitle)[^"]*"[^>]*>\s*(.*?)\s*</(?:h4|a)>'
    location_pattern = r'<span[^>]*class="[^"]*(?:job-location|job-search-card__location)[^"]*"[^>]*>\s*(.*?)\s*</span>'

    titles = re.findall(title_pattern, html, re.DOTALL)
    companies = re.findall(company_pattern, html, re.DOTALL)
    locations = re.findall(location_pattern, html, re.DOTALL)

    for i in range(min(len(titles), len(companies))):
        title = re.sub(r'<[^>]+>', '', titles[i]).strip()
        company = re.sub(r'<[^>]+>', '', companies[i]).strip()
        location = re.sub(r'<[^>]+>', '', locations[i]).strip() if i < len(locations) else "Finland"
        if title and company:
            jobs.append({
                "title": title,
                "company": company,
                "location": location,
            })

    return jobs[:10]  # Limit to top 10 per search


def generate_report():
    """Generate the daily job report."""
    report_lines = [
        f"# Job Tracker - {TODAY}",
        "",
        f"*Auto-generated daily job search for Senior Software Engineer / Cloud Architect / DevOps roles in Espoo/Helsinki, Finland*",
        "",
    ]

    all_jobs = []

    for search in SEARCHES:
        report_lines.append(f"## {search['category']}")
        report_lines.append("")
        report_lines.append("| Search | Job Count | Apply Link |")
        report_lines.append("|---|---|---|")

        for name, url in search["queries"]:
            print(f"Fetching: {name}...")
            html = fetch_page(url)
            count = extract_job_count(html)
            jobs = extract_jobs_from_html(html)
            all_jobs.extend(jobs)
            report_lines.append(f"| {name} | {count} | [Search on LinkedIn]({url}) |")

        report_lines.append("")

        # If we found specific jobs, list them
        category_jobs = extract_jobs_from_html(html) if html else []
        if category_jobs:
            report_lines.append(f"### Recent Listings")
            report_lines.append("")
            report_lines.append("| Company | Role | Location |")
            report_lines.append("|---|---|---|")
            for job in category_jobs[:5]:
                is_target = any(tc.lower() in job["company"].lower() for tc in TARGET_COMPANIES)
                prefix = "**" if is_target else ""
                suffix = "**" if is_target else ""
                report_lines.append(f"| {prefix}{job['company']}{suffix} | {job['title']} | {job['location']} |")
            report_lines.append("")

    # Target companies section
    report_lines.extend([
        "## Target Companies to Watch",
        "",
        "These stable companies in Espoo/Helsinki frequently hire for matching roles:",
        "",
        "| Company | HQ | Why Apply | Careers Page |",
        "|---|---|---|---|",
        "| **Nokia** | Espoo | Fortune 500, cloud/5G | [Careers](https://www.nokia.com/careers/) |",
        "| **KONE** | Espoo | IoT/Cloud, 60K employees | [Careers](https://www.kone.com/en/careers/) |",
        "| **Nordea** | Helsinki | Banking, Java/Spring domain match | [Careers](https://www.nordea.com/en/careers) |",
        "| **TietoEVRY** | Espoo | Largest Nordic IT, 24K employees | [Careers](https://www.tietoevry.com/en/careers/) |",
        "| **Trimble** | Espoo | AWS/Cloud focus | [Careers](https://www.trimble.com/careers) |",
        "| **Siemens** | Espoo | Industrial cloud | [Careers](https://www.siemens.com/global/en/company/jobs.html) |",
        "| **Reaktor** | Helsinki | Premium consultancy | [Careers](https://www.reaktor.com/careers/) |",
        "| **Gofore** | Helsinki | Listed, growing | [Careers](https://gofore.com/en/careers/) |",
        "| **AlphaSense** | Helsinki | AI/Search, well-funded | [Careers](https://www.alpha-sense.com/careers/) |",
        "| **Aiven** | Helsinki | Cloud-native DB | [Careers](https://aiven.io/careers) |",
        "",
    ])

    # Quick links
    report_lines.extend([
        "## Quick Apply Links",
        "",
        "1. [Java Developer jobs Finland](https://fi.linkedin.com/jobs/java-developer-jobs)",
        "2. [DevOps jobs Finland](https://fi.linkedin.com/jobs/devops-jobs)",
        "3. [Cloud Architect jobs Finland](https://fi.linkedin.com/jobs/cloud-architect-jobs)",
        "4. [AWS Cloud Architect jobs Finland](https://fi.linkedin.com/jobs/aws-cloud-architect-jobs)",
        "5. [Staff Engineer jobs Finland](https://fi.linkedin.com/jobs/staff-engineer-jobs)",
        "6. [Principal Software Engineer Finland](https://fi.linkedin.com/jobs/principal-software-engineer-jobs)",
        "7. [Spring Boot jobs Finland](https://fi.linkedin.com/jobs/spring-boot-jobs-finland)",
        "8. [Software Architect jobs Finland](https://fi.linkedin.com/jobs/software-architect-jobs)",
        "9. [Kubernetes jobs Finland](https://fi.linkedin.com/jobs/kubernetes-jobs)",
        "10. [Cloud Engineer jobs Finland](https://fi.linkedin.com/jobs/cloud-engineer-jobs)",
        "",
        "---",
        f"*Generated on {TODAY} by [Job Tracker](https://github.com/gauravs08/job-tracker)*",
    ])

    return "\n".join(report_lines)


def send_email(report_md):
    """Send the job report via Gmail SMTP."""
    gmail_user = os.environ.get("GMAIL_USER", "")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    recipient = os.environ.get("RECIPIENT_EMAIL", "sharmagauravs08@gmail.com")

    print(f"[DEBUG] GMAIL_USER is {'set' if gmail_user else 'EMPTY'} (length: {len(gmail_user)})")
    print(f"[DEBUG] GMAIL_APP_PASSWORD is {'set' if gmail_app_password else 'EMPTY'} (length: {len(gmail_app_password)})")

    if not gmail_user or not gmail_app_password:
        print("[SKIP] Email credentials not configured. Set GMAIL_USER and GMAIL_APP_PASSWORD secrets in GitHub repo settings.")
        print("[SKIP] Go to: Settings > Secrets and variables > Actions > New repository secret")
        return False

    # Convert markdown to simple HTML for email
    html_body = report_md
    # Basic markdown to HTML conversion
    html_body = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html_body, flags=re.MULTILINE)
    html_body = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html_body, flags=re.MULTILINE)
    html_body = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html_body, flags=re.MULTILINE)
    html_body = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_body)
    html_body = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html_body)
    html_body = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html_body)
    html_body = html_body.replace("\n", "<br>\n")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Daily Job Tracker Report - {TODAY}"
    msg["From"] = gmail_user
    msg["To"] = recipient

    msg.attach(MIMEText(report_md, "plain"))
    msg.attach(MIMEText(f"<html><body>{html_body}</body></html>", "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_app_password)
            server.sendmail(gmail_user, recipient, msg.as_string())
        print(f"[OK] Email sent to {recipient}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")
        return False


def save_report(report_md):
    """Save report to jobs/ directory."""
    filepath = f"jobs/Jobs-{TODAY}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"[OK] Report saved to {filepath}")
    return filepath


def main():
    print(f"=== Job Tracker - {TODAY} ===")
    print()

    report = generate_report()
    filepath = save_report(report)
    send_email(report)

    print()
    print(f"Done! Report: {filepath}")


if __name__ == "__main__":
    main()
