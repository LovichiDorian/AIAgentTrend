"""
TechDaily Pro v3 - Email Startups (SÉPARÉ)

Envoie un deuxième email dédié aux startups détectées.
Email 1 = Veille Tech (format original)
Email 2 = Startups Tech (ce module)
"""

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict, Optional
import re


def send_startup_email(
    startups: List[Dict],
    yc_batch: Optional[str] = None,
    yc_batch_url: Optional[str] = None,
    sources_scraped: List[str] = None,
    to_email: str = None,
) -> bool:
    """
    Envoie l'email STARTUPS séparé.
    
    Args:
        startups: Liste des startups détectées
        yc_batch: Batch YC auto-détecté (ex: "W26")
        yc_batch_url: URL du batch YC
        sources_scraped: Liste des sources scrapées
        to_email: Email destinataire
    
    Returns:
        True si envoi réussi
    """
    # Configuration SMTP
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    email_username = os.environ.get("SMTP_USER") or os.environ.get("EMAIL_USERNAME")
    email_password = os.environ.get("SMTP_PASS") or os.environ.get("EMAIL_PASSWORD")
    
    if to_email is None:
        to_email = os.environ.get("TO_EMAIL", "")
    
    if not email_username or not email_password:
        print("⚠️ SMTP non configuré - email startups non envoyé")
        return False
    
    if not to_email:
        print("⚠️ TO_EMAIL non configuré - email startups non envoyé")
        return False
    
    if not startups:
        print("ℹ️ Aucune startup détectée - email startups non envoyé")
        return False
    
    # Sujet
    today = datetime.now().strftime("%d/%m/%Y")
    subject = f"🚀 Startups Tech du {today}"
    if yc_batch:
        subject += f" | YC {yc_batch} détecté"
    
    # Générer le contenu markdown
    markdown_content = generate_startup_markdown(startups, yc_batch, yc_batch_url, sources_scraped)
    
    # Créer le message
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"TechDaily Pro - Startups <{email_username}>"
    message["To"] = to_email
    
    # Version texte
    text_part = MIMEText(markdown_content, "plain", "utf-8")
    
    # Version HTML
    html_content = startup_markdown_to_html(markdown_content, yc_batch)
    html_part = MIMEText(html_content, "html", "utf-8")
    
    message.attach(text_part)
    message.attach(html_part)
    
    # Envoyer
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(email_username, email_password)
            server.sendmail(email_username, to_email, message.as_string())
        
        print(f"✅ Email STARTUPS envoyé à {to_email}")
        return True
    
    except Exception as e:
        print(f"❌ Erreur envoi email startups: {e}")
        return False


def generate_startup_markdown(
    startups: List[Dict],
    yc_batch: Optional[str],
    yc_batch_url: Optional[str],
    sources_scraped: List[str]
) -> str:
    """Génère le contenu markdown pour l'email startups."""
    
    date_str = datetime.now().strftime("%d/%m/%Y")
    lines = [f"# 🚀 Startups Tech Détectées - {date_str}\n"]
    
    # Info batch YC
    if yc_batch:
        lines.append(f"🎯 **Batch YC auto-détecté**: {yc_batch}")
        if yc_batch_url:
            lines.append(f"   → {yc_batch_url}")
        lines.append("")
    
    # Stats
    lines.append(f"📊 **{len(startups)} startups** détectées depuis {len(sources_scraped or [])} sources\n")
    
    # Tableau des startups
    lines.append("## 🚀 Startups du jour\n")
    lines.append("| Startup | Incubateur | Description | Funding | Lien |")
    lines.append("|---------|------------|-------------|---------|------|")
    
    for startup in startups[:20]:  # Max 20
        name = startup.get("name", "?")
        incubator = startup.get("incubator", "-")
        desc = startup.get("description", "-")[:60]
        funding = startup.get("funding", "-")
        url = startup.get("url", "")
        
        link = f"[Site]({url})" if url else "-"
        lines.append(f"| {name} | {incubator} | {desc} | {funding} | {link} |")
    
    # Grouper par incubateur
    lines.append("\n## 📈 Répartition par source\n")
    incubator_counts = {}
    for s in startups:
        inc = s.get("incubator", "Autre")
        incubator_counts[inc] = incubator_counts.get(inc, 0) + 1
    
    for inc, count in sorted(incubator_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- **{inc}**: {count} startup(s)")
    
    # Sources
    if sources_scraped:
        lines.append(f"\n---\n📡 Sources scrapées: {', '.join(sources_scraped)}")
    
    lines.append(f"⏰ Timestamp: {datetime.now().strftime('%d/%m/%Y %H:%M CET')}")
    
    return "\n".join(lines)


def startup_markdown_to_html(markdown: str, yc_batch: Optional[str] = None) -> str:
    """Convertit le markdown startups en HTML."""
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 700px;
                margin: 0 auto;
                padding: 20px;
                line-height: 1.6;
                color: #1a1a2e;
                background: #f0f4f8;
            }}
            .container {{
                background: white;
                border-radius: 16px;
                padding: 0;
                box-shadow: 0 4px 24px rgba(0,0,0,0.08);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #ff6b6b 0%, #feca57 100%);
                color: white;
                padding: 28px 24px;
                text-align: center;
            }}
            .header h1 {{
                color: white;
                margin: 0 0 8px 0;
                font-size: 26px;
                font-weight: 700;
            }}
            .header .subtitle {{
                opacity: 0.95;
                font-size: 14px;
            }}
            .batch-badge {{
                display: inline-block;
                background: rgba(255,255,255,0.25);
                padding: 6px 16px;
                border-radius: 20px;
                font-size: 14px;
                font-weight: 600;
                margin-top: 12px;
            }}
            .content {{
                padding: 24px;
            }}
            h2 {{
                color: #1a1a2e;
                font-size: 18px;
                margin-top: 24px;
                border-bottom: 2px solid #ff6b6b;
                padding-bottom: 8px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 16px 0;
                font-size: 13px;
            }}
            th {{
                background: linear-gradient(135deg, #ff6b6b 0%, #feca57 100%);
                color: white;
                padding: 12px 8px;
                text-align: left;
                font-weight: 600;
            }}
            td {{
                padding: 12px 8px;
                border-bottom: 1px solid #eee;
            }}
            tr:hover td {{
                background: #fff5f5;
            }}
            a {{
                color: #ff6b6b;
                text-decoration: none;
                font-weight: 500;
            }}
            a:hover {{
                text-decoration: underline;
            }}
            .stats {{
                background: linear-gradient(135deg, #fff5f5 0%, #fffbf0 100%);
                padding: 16px;
                border-radius: 10px;
                margin: 16px 0;
            }}
            ul {{
                padding-left: 20px;
            }}
            li {{
                margin: 8px 0;
            }}
            .footer {{
                color: #888;
                font-size: 12px;
                padding: 20px 24px;
                border-top: 1px solid #eee;
                text-align: center;
                background: #fafafa;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 Startups Tech Détectées</h1>
                <div class="subtitle">{datetime.now().strftime("%d/%m/%Y")}</div>
                {f'<div class="batch-badge">🎯 YC {yc_batch} auto-détecté</div>' if yc_batch else ''}
            </div>
            
            <div class="content">
                {simple_md_to_html(markdown)}
            </div>
            
            <div class="footer">
                <p>🤖 TechDaily Pro v3 - Email Startups</p>
                <p>Auto-détection YC batch | 6 sources scrapées</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html


def simple_md_to_html(md: str) -> str:
    """Conversion markdown simplifiée."""
    html = md
    
    # Skip le titre principal (déjà dans le header)
    html = re.sub(r'^# .+$', '', html, flags=re.MULTILINE)
    
    # Headers
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    
    # Bold
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    
    # Links
    html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html)
    
    # Tables
    lines = html.split('\n')
    result = []
    in_table = False
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and stripped.endswith('|'):
            if not in_table:
                in_table = True
                result.append('<table>')
                # Header row
                cols = [c.strip() for c in stripped.split('|')[1:-1]]
                result.append('<thead><tr>')
                for col in cols:
                    result.append(f'<th>{col}</th>')
                result.append('</tr></thead><tbody>')
            elif '---' in stripped:
                continue  # Skip separator
            else:
                cols = [c.strip() for c in stripped.split('|')[1:-1]]
                result.append('<tr>')
                for col in cols:
                    col = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', col)
                    result.append(f'<td>{col}</td>')
                result.append('</tr>')
        else:
            if in_table:
                result.append('</tbody></table>')
                in_table = False
            result.append(line)
    
    if in_table:
        result.append('</tbody></table>')
    
    html = '\n'.join(result)
    
    # Lists
    lines = html.split('\n')
    result = []
    in_list = False
    
    for line in lines:
        if line.strip().startswith('- '):
            if not in_list:
                result.append('<ul>')
                in_list = True
            result.append(f'<li>{line.strip()[2:]}</li>')
        else:
            if in_list:
                result.append('</ul>')
                in_list = False
            result.append(line)
    
    if in_list:
        result.append('</ul>')
    
    return '\n'.join(result)
