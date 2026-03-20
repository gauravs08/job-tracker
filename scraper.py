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
    """Extract job titles, company names, locations, and job URLs from LinkedIn HTML."""
    jobs = []

    # Method 1: Extract from job card links (most reliable for getting URLs)
    # LinkedIn job cards wrap titles in <a> tags with href to the job page
    card_pattern = r'<a[^>]*href="(https?://[^"]*linkedin\.com/jobs/view/[^"]*)"[^>]*class="[^"]*base-card__full-link[^"]*"[^>]*>'
    card_urls = re.findall(card_pattern, html, re.DOTALL)

    # Also try alternate URL patterns
    if not card_urls:
        card_pattern2 = r'href="(https?://[^"]*linkedin\.com/jobs/view/[^"]*)"'
        card_urls = re.findall(card_pattern2, html, re.DOTALL)

    # Extract job details
    title_pattern = r'<(?:h3|span)[^>]*class="[^"]*(?:job-title|base-search-card__title)[^"]*"[^>]*>\s*(.*?)\s*</(?:h3|span)>'
    company_pattern = r'<(?:h4|a)[^>]*class="[^"]*(?:company-name|base-search-card__subtitle)[^"]*"[^>]*>\s*(.*?)\s*</(?:h4|a)>'
    location_pattern = r'<span[^>]*class="[^"]*(?:job-location|job-search-card__location)[^"]*"[^>]*>\s*(.*?)\s*</span>'

    titles = re.findall(title_pattern, html, re.DOTALL)
    companies = re.findall(company_pattern, html, re.DOTALL)
    locations = re.findall(location_pattern, html, re.DOTALL)

    # Clean up URLs - remove tracking params
    clean_urls = []
    for url in card_urls:
        clean_url = url.split("?")[0]
        if clean_url not in clean_urls:
            clean_urls.append(clean_url)

    for i in range(min(len(titles), len(companies))):
        title = re.sub(r'<[^>]+>', '', titles[i]).strip()
        company = re.sub(r'<[^>]+>', '', companies[i]).strip()
        location = re.sub(r'<[^>]+>', '', locations[i]).strip() if i < len(locations) else "Finland"
        job_url = clean_urls[i] if i < len(clean_urls) else ""
        if title and company:
            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "url": job_url,
            })

    # Method 2: If no structured data found, try JSON-LD
    if not jobs:
        jsonld_pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
        jsonld_blocks = re.findall(jsonld_pattern, html, re.DOTALL)
        for block in jsonld_blocks:
            try:
                data = json.loads(block)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") == "JobPosting":
                        title = item.get("title", "")
                        company = item.get("hiringOrganization", {}).get("name", "")
                        loc = item.get("jobLocation", {})
                        if isinstance(loc, list):
                            loc = loc[0] if loc else {}
                        location = loc.get("address", {}).get("addressLocality", "Finland") if isinstance(loc, dict) else "Finland"
                        job_url = item.get("url", "")
                        if title and company:
                            jobs.append({
                                "title": title,
                                "company": company,
                                "location": location,
                                "url": job_url,
                            })
            except (json.JSONDecodeError, AttributeError, TypeError):
                continue

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
    seen_urls = set()  # Deduplicate jobs across searches

    for search in SEARCHES:
        report_lines.append(f"## {search['category']}")
        report_lines.append("")

        category_jobs = []
        for name, url in search["queries"]:
            print(f"Fetching: {name}...")
            html = fetch_page(url)
            jobs = extract_jobs_from_html(html)
            for job in jobs:
                job_key = f"{job['company']}|{job['title']}"
                if job_key not in seen_urls:
                    seen_urls.add(job_key)
                    category_jobs.append(job)
            print(f"  Found {len(jobs)} jobs")

        # Show search links
        report_lines.append(f"**Search links:** ", )
        search_links = " | ".join([f"[{name}]({url})" for name, url in search["queries"]])
        report_lines[-1] = f"**Search links:** {search_links}"
        report_lines.append("")

        # List individual jobs with apply links
        if category_jobs:
            report_lines.append("| Company | Role | Location | Apply |")
            report_lines.append("|---|---|---|---|")
            for job in category_jobs[:10]:
                is_target = any(tc.lower() in job["company"].lower() for tc in TARGET_COMPANIES)
                company_display = f"**{job['company']}**" if is_target else job['company']
                if job["url"]:
                    apply_link = f"[Apply]({job['url']})"
                else:
                    # Generate a LinkedIn search URL as fallback
                    search_query = urllib.parse.quote(f"{job['title']} {job['company']}")
                    fallback_url = f"https://www.linkedin.com/jobs/search/?keywords={search_query}&location=Finland"
                    apply_link = f"[Search]({fallback_url})"
                report_lines.append(f"| {company_display} | {job['title']} | {job['location']} | {apply_link} |")
            all_jobs.extend(category_jobs)
        else:
            report_lines.append("*No specific listings scraped. Use search links above to browse.*")

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
