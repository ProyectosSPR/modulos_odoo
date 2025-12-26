#!/bin/bash
#
# Script de instalación de Kafka con Strimzi para Migration Hub
# Ejecutar desde una máquina con acceso a kubectl y al cluster de Kubernetes
#
# Uso: ./install.sh [desarrollo|produccion]
#

set -e

MODE=${1:-desarrollo}
NAMESPACE="default"

echo "======================================"
echo "  Kafka Migration Hub - Instalación"
echo "  Modo: $MODE"
echo "  Namespace: $NAMESPACE"
echo "======================================"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar kubectl
if ! command -v kubectl &> /dev/null; then
    log_error "kubectl no está instalado o no está en el PATH"
    exit 1
fi

# Verificar conexión al cluster
if ! kubectl cluster-info &> /dev/null; then
    log_error "No se puede conectar al cluster de Kubernetes"
    exit 1
fi

log_info "Conectado al cluster de Kubernetes"

# Paso 1: Instalar Strimzi Operator
log_info "Instalando Strimzi Operator..."

# Verificar si ya está instalado
if kubectl get deployment strimzi-cluster-operator -n $NAMESPACE &> /dev/null; then
    log_warn "Strimzi Operator ya está instalado"
else
    kubectl create -f "https://strimzi.io/install/latest?namespace=$NAMESPACE" -n $NAMESPACE
    log_info "Esperando a que Strimzi Operator esté listo..."
    kubectl wait --for=condition=available --timeout=300s deployment/strimzi-cluster-operator -n $NAMESPACE
fi

# Paso 2: Crear cluster de Kafka
log_info "Creando cluster de Kafka..."

# Aplicar manifiesto
kubectl apply -f kafka-cluster.yaml -n $NAMESPACE

log_info "Esperando a que Kafka esté listo (puede tomar 2-5 minutos)..."
kubectl wait kafka/migration-hub --for=condition=Ready --timeout=600s -n $NAMESPACE

# Paso 3: Verificar instalación
log_info "Verificando instalación..."

echo ""
echo "======================================"
echo "  Estado del Cluster Kafka"
echo "======================================"

kubectl get kafka migration-hub -n $NAMESPACE
echo ""

kubectl get pods -l strimzi.io/cluster=migration-hub -n $NAMESPACE
echo ""

# Obtener el servicio de bootstrap
BOOTSTRAP_SERVICE=$(kubectl get service migration-hub-kafka-bootstrap -n $NAMESPACE -o jsonpath='{.spec.clusterIP}')

echo "======================================"
echo "  Configuración para Odoo"
echo "======================================"
echo ""
echo "Servicio interno (dentro del cluster):"
echo "  migration-hub-kafka-bootstrap:9092"
echo ""
echo "IP del servicio: $BOOTSTRAP_SERVICE:9092"
echo ""
echo "Para configurar en Odoo:"
echo "  1. Ir a Ajustes > Técnico > Parámetros del Sistema"
echo "  2. Buscar: migration_hub.kafka_servers"
echo "  3. Valor: migration-hub-kafka-bootstrap:9092"
echo ""

# Paso 4: Crear topics de prueba
log_info "Creando topics de prueba..."

kubectl exec -it migration-hub-kafka-0 -n $NAMESPACE -- bin/kafka-topics.sh \
    --bootstrap-server localhost:9092 \
    --create \
    --topic test-migration \
    --partitions 3 \
    --replication-factor 1 \
    --if-not-exists 2>/dev/null || true

# Listar topics
log_info "Topics disponibles:"
kubectl exec -it migration-hub-kafka-0 -n $NAMESPACE -- bin/kafka-topics.sh \
    --bootstrap-server localhost:9092 \
    --list

echo ""
echo "======================================"
echo "  Instalación Completada!"
echo "======================================"
echo ""
echo "Próximos pasos:"
echo "  1. Instalar el módulo 'kafka_migration_hub' en Odoo"
echo "  2. Verificar la conexión en el menú Migration Hub"
echo "  3. Crear un proyecto de migración de prueba"
echo ""
