#!/bin/bash

# Install RabbitMQ and Redis
echo "Bringing up rabbitmq"
#helm install rabbitmq bitnami/rabbitmq
helm install rabbitmq bitnami/rabbitmq
kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=rabbitmq --timeout=180s

echo "Bringing up redis_deployment"
kubectl apply -f deployment/redis_deployment.yaml

echo "Bringing up redis_service"
kubectl apply -f deployment/redis_service.yaml

# Deploy application services in order
echo "Bringing up event_tracker"
kubectl apply -f deployment/event_tracker_deployment.yaml

echo "Bringing up rest_server_deployment"
kubectl apply -f deployment/rest_server_deployment.yaml

echo "Bringing up rest_server_deployment"
kubectl apply -f deployment/rest_server_service.yaml

echo "Bringing up rest_server_service"
kubectl apply -f deployment/splitter_deployment.yaml

echo "Bringing up chunker_deployment"
kubectl apply -f deployment/chunker_deployment.yaml

echo "Bringing up tts_deployment"
kubectl apply -f deployment/tts_deployment.yaml

echo "Bringing up audio_stitcher_deployment"
kubectl apply -f deployment/audio_stitcher_deployment.yaml

echo "Deployment completed successfully."
