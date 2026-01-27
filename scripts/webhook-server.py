#!/usr/bin/env python3
"""
Webhook Server - Auto-deploy on GitHub push
Léger et simple pour VPS modeste
"""

import hashlib
import hmac
import json
import os
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

# Configurationn
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "your-secret-here")
REPO_PATH = os.environ.get("REPO_PATH", "/home/ubuntu/projects/AIAgentTrend")
PORT = int(os.environ.get("WEBHOOK_PORT", "9000"))


def verify_signature(payload: bytes, signature: str) -> bool:
    """Vérifie la signature HMAC du webhook GitHub."""
    if not signature:
        return False
    
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)


def deploy():
    """Exécute le déploiement."""
    print("🚀 Déploiement en cours...")
    
    commands = [
        f"cd {REPO_PATH} && git pull origin main",
        f"cd {REPO_PATH} && docker build -t tech-watch-agent:latest .",
        "docker save tech-watch-agent:latest | sudo k3s ctr images import -",
    ]
    
    for cmd in commands:
        print(f"  → {cmd}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ❌ Erreur: {result.stderr}")
            return False
        print(f"  ✅ OK")
    
    print("🎉 Déploiement terminé!")
    return True


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/webhook":
            self.send_response(404)
            self.end_headers()
            return
        
        # Lire le payload
        content_length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(content_length)
        
        # Vérifier la signature
        signature = self.headers.get("X-Hub-Signature-256", "")
        if not verify_signature(payload, signature):
            print("❌ Signature invalide")
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Invalid signature")
            return
        
        # Parser le payload
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return
        
        # Vérifier que c'est un push sur main
        ref = data.get("ref", "")
        if ref != "refs/heads/main":
            print(f"ℹ️ Ignoré: push sur {ref}")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Ignored: not main branch")
            return
        
        # Répondre immédiatement (GitHub timeout = 10s)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Deployment started")
        
        # Déployer en arrière-plan
        print(f"📦 Push détecté sur main par {data.get('pusher', {}).get('name', 'unknown')}")
        deploy()
    
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    print(f"🎯 Webhook server démarré sur port {PORT}")
    print(f"   URL: http://0.0.0.0:{PORT}/webhook")
    print(f"   Health: http://0.0.0.0:{PORT}/health")
    
    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Arrêt du serveur")
        server.shutdown()


if __name__ == "__main__":
    main()
