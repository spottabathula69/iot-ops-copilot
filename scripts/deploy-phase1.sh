#!/bin/bash
# Deploy IoT Ops Copilot - Phase 1 (Kafka Ingestion MVP)

set -e

echo "🚀 Deploying IoT Ops Copilot - Phase 1"
echo "======================================="

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. Deploy Kafka
echo -e "\n${BLUE}1. Deploying Kafka (Strimzi)${NC}"
helm repo add strimzi https://strimzi.io/charts/ || true
helm repo update

helm install strimzi-kafka-operator strimzi/strimzi-kafka-operator \
  --namespace kafka \
  --create-namespace \
  --values infra/kafka/strimzi-operator.yaml \
  --wait

echo "Waiting for Strimzi operator..."
kubectl wait --for=condition=ready pod -l name=strimzi-cluster-operator -n kafka --timeout=300s

echo "Deploying Kafka cluster..."
kubectl apply -f infra/kafka/namespace.yaml
kubectl apply -f infra/kafka/kafka-cluster.yaml

echo "Waiting for Kafka cluster..."
kubectl wait kafka/iot-ops-kafka --for=condition=Ready --timeout=600s -n kafka

echo "Creating Kafka topics..."
kubectl apply -f infra/kafka/kafka-topics.yaml

echo -e "${GREEN}✓ Kafka deployed${NC}"

# 2. Deploy Postgres
echo -e "\n${BLUE}2. Deploying Postgres${NC}"
kubectl apply -f infra/postgres/postgres.yaml
kubectl wait --for=condition=ready pod -l app=postgres -n postgres --timeout=300s
sleep 5  # Give Postgres time to fully initialize
kubectl apply -f infra/postgres/schema-init-job.yaml
kubectl wait --for=condition=complete job/postgres-schema-init -n default --timeout=120s

echo -e "${GREEN}✓ Postgres deployed and schema initialized${NC}"

# 3. Deploy MinIO
echo -e "\n${BLUE}3. Deploying MinIO${NC}"
kubectl apply -f infra/minio/minio.yaml
kubectl wait --for=condition=ready pod -l app=minio -n minio --timeout=180s

echo -e "${GREEN}✓ MinIO deployed${NC}"

# 4. Build and load simulator image
echo -e "\n${BLUE}4. Building simulator image${NC}"
docker build -t iot-simulator:latest apps/simulator/
kind load docker-image iot-simulator:latest --name iot-ops-copilot

echo -e "${GREEN}✓ Simulator image loaded${NC}"

# 5. Build and load consumer image
echo -e "\n${BLUE}5. Building consumer image${NC}"
docker build -t iot-consumer:latest apps/ingestion/
kind load docker-image iot-consumer:latest --name iot-ops-copilot

echo -e "${GREEN}✓ Consumer images loaded${NC}"

# 6. Deploy simulator
echo -e "\n${BLUE}6. Deploying IoT simulator${NC}"
kubectl apply -f apps/simulator/deployment.yaml
kubectl wait --for=condition=ready pod -l app=iot-simulator -n default --timeout=60s

echo -e "${GREEN}✓ Simulator deployed${NC}"

# 7. Deploy consumers
echo -e "\n${BLUE}7. Deploying Kafka consumers${NC}"
kubectl apply -f apps/ingestion/deployment.yaml
kubectl wait --for=condition=ready pod -l app=consumer-postgres -n default --timeout=60s
kubectl wait --for=condition=ready pod -l app=consumer-bronze -n default --timeout=60s

echo -e "${GREEN}✓ Consumers deployed${NC}"

# 8. Show status
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Phase 1 deployment complete!${NC}"
echo -e "${GREEN}========================================${NC}"

echo -e "\nCluster status:"
kubectl get pods --all-namespaces | grep -E "(kafka|postgres|minio|simulator|consumer)"

echo -e "\nKafka topics:"
kubectl exec -n kafka iot-ops-kafka-kafka-0 -- bin/kafka-topics.sh --bootstrap-server localhost:9092 --list

echo -e "\n📊 To view telemetry data:"
echo "  kubectl exec -n postgres postgres-0 -- psql -U postgres -d iot_ops -c 'SELECT COUNT(*) FROM telemetry_silver;'"

echo -e "\n🔍 To view logs:"
echo "  kubectl logs -f deployment/iot-simulator"
echo "  kubectl logs -f deployment/consumer-postgres"
echo "  kubectl logs -f deployment/consumer-bronze"

echo -e "\n🌐 To access services:"
echo "  MinIO Console: kubectl port-forward -n minio svc/minio 9001:9001"
echo "  Then open: http://localhost:9001 (minioadmin/minioadmin)"

echo -e "\n✨ Done!"
