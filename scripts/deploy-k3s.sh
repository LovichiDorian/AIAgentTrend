#!/bin/bash
# =============================================================================
# Script de déploiement k3s - Tech Watch Agent
# Exécuter sur le VPS Oracle Cloud (Ubuntu)
# =============================================================================

set -e

echo "🚀 Déploiement Tech Watch Agent sur k3s"
echo "========================================"

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 1. Vérifier que k3s est installé
if ! command -v kubectl &> /dev/null; then
    echo -e "${YELLOW}⚠️  k3s non détecté. Installation...${NC}"
    curl -sfL https://get.k3s.io | sh -
    
    # Configurer kubectl pour l'utilisateur courant
    mkdir -p ~/.kube
    sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
    sudo chown $(id -u):$(id -g) ~/.kube/config
    export KUBECONFIG=~/.kube/config
    echo 'export KUBECONFIG=~/.kube/config' >> ~/.bashrc
    
    echo -e "${GREEN}✅ k3s installé${NC}"
fi

# 2. Vérifier que Docker est installé (pour build)
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}⚠️  Docker non détecté. Installation...${NC}"
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo -e "${GREEN}✅ Docker installé (reconnexion nécessaire)${NC}"
fi

# 3. Se placer dans le répertoire du projet
cd ~/AIAgentTrend

# 4. Build l'image Docker
echo -e "${YELLOW}🔨 Build de l'image Docker...${NC}"
docker build -t tech-watch-agent:latest .

# 5. Importer l'image dans k3s (containerd)
echo -e "${YELLOW}📦 Import de l'image dans k3s...${NC}"
docker save tech-watch-agent:latest | sudo k3s ctr images import -

# 6. Créer le namespace (optionnel)
kubectl create namespace tech-watch --dry-run=client -o yaml | kubectl apply -f -

# 7. Demander les clés API
echo ""
echo -e "${YELLOW}🔑 Configuration des clés API${NC}"

if [ -z "$GOOGLE_API_KEY" ]; then
    read -p "Entrez votre GOOGLE_API_KEY: " GOOGLE_API_KEY
fi

if [ -z "$MISTRAL_API_KEY" ]; then
    read -p "Entrez votre MISTRAL_API_KEY: " MISTRAL_API_KEY
fi

# 8. Créer le secret (supprimer l'ancien si existe)
kubectl delete secret tech-watch-secrets --ignore-not-found
kubectl create secret generic tech-watch-secrets \
    --from-literal=GOOGLE_API_KEY="$GOOGLE_API_KEY" \
    --from-literal=MISTRAL_API_KEY="$MISTRAL_API_KEY"

echo -e "${GREEN}✅ Secret créé${NC}"

# 9. Appliquer les manifests k8s
echo -e "${YELLOW}🚀 Déploiement des ressources Kubernetes...${NC}"
kubectl apply -f k8s/cronjob.yaml
kubectl apply -f k8s/service.yaml

echo ""
echo -e "${GREEN}✅ Déploiement terminé !${NC}"
echo ""
echo "📋 Commandes utiles :"
echo "  kubectl get cronjobs              # Voir les CronJobs"
echo "  kubectl get pods                  # Voir les pods"
echo "  kubectl logs -l app=tech-watch    # Voir les logs"
echo "  kubectl create job --from=cronjob/tech-watch-daily test-run  # Test manuel"
echo ""
