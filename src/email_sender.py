"""
Module d'envoi d'email pour la veille tech
"""

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path


def send_veille_email(
    markdown_content: str,
    to_email: str = "dorianppl852@gmail.com",
    subject: str = None
) -> bool:
    """
    Envoie la veille par email.
    
    Args:
        markdown_content: Contenu markdown de la veille
        to_email: Adresse email destinataire
        subject: Sujet de l'email (auto-généré si None)
    
    Returns:
        True si l'envoi a réussi, False sinon
    """
    # Configuration SMTP
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    email_username = os.environ.get("EMAIL_USERNAME")
    email_password = os.environ.get("EMAIL_PASSWORD")
    
    if not email_username or not email_password:
        print("⚠️ EMAIL_USERNAME ou EMAIL_PASSWORD non configurés - email non envoyé")
        return False
    
    # Sujet par défaut
    if subject is None:
        today = datetime.now().strftime("%Y-%m-%d")
        subject = f"🔍 Veille Tech du {today}"
    
    # Créer le message
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"Tech Watch Agent <{email_username}>"
    message["To"] = to_email
    
    # Version texte (markdown brut)
    text_part = MIMEText(markdown_content, "plain", "utf-8")
    
    # Version HTML
    html_content = markdown_to_html(markdown_content)
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
        
        print(f"✅ Email envoyé à {to_email}")
        return True
    
    except Exception as e:
        print(f"❌ Erreur envoi email: {e}")
        return False


def markdown_to_html(markdown: str) -> str:
    """Convertit le markdown en HTML simple."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                line-height: 1.6;
                color: #333;
            }}
            h1, h2, h3 {{
                color: #1a1a1a;
                border-bottom: 1px solid #eee;
                padding-bottom: 10px;
            }}
            h1 {{ font-size: 24px; }}
            h2 {{ font-size: 20px; }}
            h3 {{ font-size: 16px; }}
            a {{
                color: #0066cc;
                text-decoration: none;
            }}
            a:hover {{
                text-decoration: underline;
            }}
            ul {{
                padding-left: 20px;
            }}
            li {{
                margin: 8px 0;
            }}
            code {{
                background: #f5f5f5;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 14px;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 20px;
                text-align: center;
            }}
            .header h1 {{
                color: white;
                border: none;
                margin: 0;
            }}
            .footer {{
                color: #666;
                font-size: 12px;
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #eee;
                text-align: center;
            }}
            .stats {{
                background: #f8f9fa;
                padding: 10px 15px;
                border-radius: 5px;
                margin: 15px 0;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🔍 Veille Tech Quotidienne</h1>
            <p>Générée le {datetime.now().strftime("%d/%m/%Y à %H:%M")}</p>
        </div>
        
        <div class="content">
            {simple_markdown_to_html(markdown)}
        </div>
        
        <div class="footer">
            <p>🤖 Généré automatiquement par Tech Watch Agent</p>
            <p>Hébergé sur VPS Oracle Cloud avec k3s</p>
        </div>
    </body>
    </html>
    """
    return html


def simple_markdown_to_html(md: str) -> str:
    """Conversion markdown simplifiée."""
    import re
    
    html = md
    
    # Headers
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    
    # Bold
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    
    # Links
    html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html)
    
    # Lists
    lines = html.split('\n')
    in_list = False
    result = []
    
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
    
    html = '\n'.join(result)
    
    # Line breaks
    html = re.sub(r'\n\n+', '</p><p>', html)
    html = f'<p>{html}</p>'
    
    # Stats line
    html = re.sub(r'📊 \*\*Stats\*\*: (.+)', r'<div class="stats">📊 <strong>Stats</strong>: \1</div>', html)
    
    return html


def send_veille_from_file(filepath: str, to_email: str = "dorianppl852@gmail.com") -> bool:
    """Envoie la veille depuis un fichier markdown."""
    path = Path(filepath)
    if not path.exists():
        print(f"❌ Fichier non trouvé: {filepath}")
        return False
    
    content = path.read_text(encoding="utf-8")
    return send_veille_email(content, to_email)
