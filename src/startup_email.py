"""
Module d'envoi d'email pour les STARTUPS - VERSION AMÉLIORÉE

Contenu de l'email :
- 🚀 Startups de la semaine (nouvelles incubées/fundées)
- 📅 Rappels du mois (startups détectées ce mois)
- 💰 Montants de financement
- 📝 Descriptions détaillées
- 🌍 Répartition géographique
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
    startups_week: List[Dict],
    startups_month: List[Dict] = None,
    yc_batch: Optional[str] = None,
    yc_batch_url: Optional[str] = None,
    sources_scraped: List[str] = None,
    total_sources: int = 12,
    to_email: str = None,
) -> bool:
    """
    Envoie l'email STARTUPS avec descriptions et montants.
    """
    # Configuration SMTP
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    email_username = os.environ.get("EMAIL_USERNAME")
    email_password = os.environ.get("EMAIL_PASSWORD")
    
    if to_email is None:
        to_email = os.environ.get("TO_EMAIL", email_username)
    
    if not email_username or not email_password:
        print("⚠️ EMAIL_USERNAME/PASSWORD non configurés - email startups non envoyé")
        return False
    
    if not startups_week:
        print("ℹ️ Aucune startup détectée - email startups non envoyé")
        return False
    
    # Sujet
    today = datetime.now().strftime("%d/%m/%Y")
    subject = f"🚀 {len(startups_week)} Startups Tech Détectées - {today}"
    if yc_batch:
        subject = f"🚀 {len(startups_week)} Startups | YC {yc_batch} - {today}"
    
    # Contenu
    html_content = generate_startup_html(
        startups_week, 
        startups_month or [], 
        yc_batch, 
        yc_batch_url, 
        sources_scraped or [],
        total_sources
    )
    
    # Message
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"Startup Watch <{email_username}>"
    message["To"] = to_email
    
    # Version texte simple
    text_content = generate_text_version(startups_week, startups_month or [], yc_batch)
    text_part = MIMEText(text_content, "plain", "utf-8")
    html_part = MIMEText(html_content, "html", "utf-8")
    
    message.attach(text_part)
    message.attach(html_part)
    
    # Envoi
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(email_username, email_password)
            server.sendmail(email_username, to_email, message.as_string())
        
        print(f"✅ Email STARTUPS envoyé à {to_email} ({len(startups_week)} startups)")
        return True
    except Exception as e:
        print(f"❌ Erreur envoi email startups: {e}")
        return False


def generate_text_version(
    startups_week: List[Dict],
    startups_month: List[Dict],
    yc_batch: Optional[str]
) -> str:
    """Version texte plain de l'email."""
    lines = [
        f"🚀 STARTUPS TECH - {datetime.now().strftime('%d/%m/%Y')}",
        "=" * 50,
        ""
    ]
    
    if yc_batch:
        lines.append(f"🎯 Batch YC auto-détecté: {yc_batch}")
        lines.append("")
    
    lines.append(f"📊 {len(startups_week)} startups détectées cette semaine")
    lines.append("")
    lines.append("🚀 STARTUPS DE LA SEMAINE")
    lines.append("-" * 30)
    
    for s in startups_week[:25]:
        lines.append(f"\n• {s.get('name', '?')}")
        lines.append(f"  Incubateur: {s.get('incubator', '-')}")
        lines.append(f"  Funding: {s.get('funding', '-')}")
        lines.append(f"  Pays: {s.get('country', '-')}")
        desc = s.get('description', '')[:100]
        if desc:
            lines.append(f"  Description: {desc}...")
        if s.get('url'):
            lines.append(f"  Lien: {s.get('url')}")
    
    if startups_month:
        lines.append("")
        lines.append("📅 RAPPELS DU MOIS")
        lines.append("-" * 30)
        for s in startups_month[:10]:
            lines.append(f"• {s.get('name')} ({s.get('incubator')}) - {s.get('first_seen', '')}")
    
    return "\n".join(lines)


def generate_startup_html(
    startups_week: List[Dict],
    startups_month: List[Dict],
    yc_batch: Optional[str],
    yc_batch_url: Optional[str],
    sources: List[str],
    total_sources: int
) -> str:
    """Génère le HTML de l'email startups."""
    
    date_str = datetime.now().strftime("%d/%m/%Y")
    
    # Statistiques par pays
    countries = {}
    for s in startups_week:
        c = s.get("country", "Global")
        countries[c] = countries.get(c, 0) + 1
    
    # Statistiques par source
    by_source = {}
    for s in startups_week:
        src = s.get("incubator", "Autre")
        by_source[src] = by_source.get(src, 0) + 1
    
    # Table des startups
    startup_rows = ""
    for s in startups_week[:30]:
        name = s.get("name", "?")
        incubator = s.get("incubator", "-")
        funding = s.get("funding", "-") or "-"
        country = s.get("country", "-")
        desc = (s.get("description") or "-")[:120]
        url = s.get("url", "")
        
        # Badge couleur selon funding
        funding_color = "#28a745" if "$" in str(funding) or "€" in str(funding) else "#6c757d"
        
        startup_rows += f"""
        <tr>
            <td style="padding: 12px 10px; border-bottom: 1px solid #eee;">
                <strong style="color: #1a1a2e;">{name}</strong>
                {f'<br><a href="{url}" style="color: #667eea; font-size: 11px;">🔗 Site</a>' if url else ''}
            </td>
            <td style="padding: 12px 8px; border-bottom: 1px solid #eee;">
                <span style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px;">{incubator}</span>
            </td>
            <td style="padding: 12px 8px; border-bottom: 1px solid #eee;">
                <span style="background: {funding_color}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold;">{funding}</span>
            </td>
            <td style="padding: 12px 8px; border-bottom: 1px solid #eee; font-size: 12px;">{country}</td>
            <td style="padding: 12px 8px; border-bottom: 1px solid #eee; font-size: 12px; color: #555; max-width: 250px;">{desc}</td>
        </tr>
        """
    
    # Section rappels du mois
    monthly_section = ""
    if startups_month:
        monthly_rows = ""
        for s in startups_month[:15]:
            monthly_rows += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #f0f0f0;">{s.get('name', '?')}</td>
                <td style="padding: 8px; border-bottom: 1px solid #f0f0f0;">{s.get('incubator', '-')}</td>
                <td style="padding: 8px; border-bottom: 1px solid #f0f0f0;">{s.get('funding', '-')}</td>
                <td style="padding: 8px; border-bottom: 1px solid #f0f0f0;">{s.get('first_seen', '-')}</td>
            </tr>
            """
        
        monthly_section = f"""
        <div style="margin-top: 32px;">
            <h2 style="color: #1a1a2e; font-size: 18px; border-left: 4px solid #feca57; padding-left: 12px; margin-bottom: 16px;">
                📅 Rappels du mois ({len(startups_month)} startups)
            </h2>
            <p style="color: #666; font-size: 13px; margin-bottom: 12px;">
                Startups détectées ce mois-ci que vous avez peut-être manquées
            </p>
            <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
                <thead>
                    <tr style="background: #f8f9fa;">
                        <th style="padding: 10px 8px; text-align: left;">Startup</th>
                        <th style="padding: 10px 8px; text-align: left;">Source</th>
                        <th style="padding: 10px 8px; text-align: left;">Funding</th>
                        <th style="padding: 10px 8px; text-align: left;">Détecté le</th>
                    </tr>
                </thead>
                <tbody>
                    {monthly_rows}
                </tbody>
            </table>
        </div>
        """
    
    # Stats par pays
    country_stats = ""
    for c, count in sorted(countries.items(), key=lambda x: -x[1])[:6]:
        country_stats += f'<span style="display: inline-block; margin: 4px 6px; padding: 4px 10px; background: #f0f4f8; border-radius: 12px; font-size: 12px;">{c}: <strong>{count}</strong></span>'
    
    # Stats par source
    source_stats = ""
    for src, count in sorted(by_source.items(), key=lambda x: -x[1])[:8]:
        source_stats += f'<span style="display: inline-block; margin: 4px 6px; padding: 4px 10px; background: #e8f4f8; border-radius: 12px; font-size: 11px;">{src}: <strong>{count}</strong></span>'
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; line-height: 1.6; color: #1a1a2e; background: #f5f7fa;">
        
        <div style="background: white; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.08);">
            
            <!-- HEADER -->
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #ff6b6b 100%); color: white; padding: 32px 24px; text-align: center;">
                <h1 style="margin: 0 0 8px 0; font-size: 28px; color: white;">🚀 Startups Tech</h1>
                <div style="font-size: 16px; opacity: 0.9;">{date_str}</div>
                
                <!-- Stats badges -->
                <div style="margin-top: 20px;">
                    <span style="display: inline-block; background: rgba(255,255,255,0.2); padding: 8px 16px; border-radius: 20px; margin: 4px; font-size: 14px;">
                        📊 <strong>{len(startups_week)}</strong> startups détectées
                    </span>
                    <span style="display: inline-block; background: rgba(255,255,255,0.2); padding: 8px 16px; border-radius: 20px; margin: 4px; font-size: 14px;">
                        🔍 <strong>{len(sources)}/{total_sources}</strong> sources scrapées
                    </span>
                    {f'<span style="display: inline-block; background: rgba(255,107,107,0.8); padding: 8px 16px; border-radius: 20px; margin: 4px; font-size: 14px;"><strong>🎯 YC {yc_batch}</strong> auto-détecté</span>' if yc_batch else ''}
                </div>
            </div>
            
            <!-- CONTENT -->
            <div style="padding: 24px;">
                
                <!-- Répartition géographique -->
                <div style="margin-bottom: 24px; padding: 16px; background: #f8f9fa; border-radius: 12px;">
                    <h3 style="margin: 0 0 12px 0; font-size: 14px; color: #666;">🌍 Répartition géographique</h3>
                    {country_stats}
                </div>
                
                <!-- Répartition par source -->
                <div style="margin-bottom: 24px; padding: 16px; background: #f0f8ff; border-radius: 12px;">
                    <h3 style="margin: 0 0 12px 0; font-size: 14px; color: #666;">📡 Par incubateur/source</h3>
                    {source_stats}
                </div>
                
                <!-- TABLE PRINCIPALE -->
                <h2 style="color: #1a1a2e; font-size: 18px; border-left: 4px solid #667eea; padding-left: 12px; margin: 24px 0 16px 0;">
                    🚀 Startups de la semaine
                </h2>
                
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                        <thead>
                            <tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                                <th style="padding: 14px 10px; text-align: left; color: white; font-weight: 600;">Startup</th>
                                <th style="padding: 14px 8px; text-align: left; color: white; font-weight: 600;">Source</th>
                                <th style="padding: 14px 8px; text-align: left; color: white; font-weight: 600;">💰 Funding</th>
                                <th style="padding: 14px 8px; text-align: left; color: white; font-weight: 600;">🌍 Pays</th>
                                <th style="padding: 14px 8px; text-align: left; color: white; font-weight: 600;">📝 Description</th>
                            </tr>
                        </thead>
                        <tbody>
                            {startup_rows}
                        </tbody>
                    </table>
                </div>
                
                {monthly_section}
                
                <!-- YC Batch Link -->
                {f'''
                <div style="margin-top: 24px; padding: 16px; background: linear-gradient(135deg, #ff6b6b 0%, #feca57 100%); border-radius: 12px; text-align: center;">
                    <span style="color: white; font-size: 14px;">🎯 Explorer toutes les startups YC {yc_batch}</span><br>
                    <a href="{yc_batch_url}" style="color: white; font-weight: bold; font-size: 16px;">→ Voir sur Y Combinator</a>
                </div>
                ''' if yc_batch and yc_batch_url else ''}
                
            </div>
            
            <!-- FOOTER -->
            <div style="padding: 20px 24px; border-top: 1px solid #eee; background: #fafafa; text-align: center;">
                <div style="color: #888; font-size: 12px;">
                    🤖 Startup Watch - Email automatique<br>
                    Sources: {', '.join(sources)}<br>
                    ⏰ {datetime.now().strftime('%d/%m/%Y %H:%M CET')}
                </div>
            </div>
            
        </div>
        
    </body>
    </html>
    """
