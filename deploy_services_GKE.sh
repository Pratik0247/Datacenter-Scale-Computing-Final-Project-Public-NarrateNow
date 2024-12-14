#!/bin/bash

# Install RabbitMQ and Redis
echo "Bringing up rabbitmq"
#helm install rabbitmq bitnami/rabbitmq
helm install rabbitmq bitnami/rabbitmq
kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=rabbitmq --timeout=180s

echo "Bringing up redis_deployment"
kubectl apply -f deployment/GKE/GKE_redis_deployment.yaml

echo "Bringing up redis_service"
kubectl apply -f deployment/GKE/GKE_redis_service.yaml

# Deploy application services in order
echo "Bringing up event_tracker"
kubectl apply -f deployment/GKE/GKE_event_tracker_deployment.yaml

echo "Bringing up rest_server_deployment"
kubectl apply -f deployment/GKE/GKE_rest_server_deployment.yaml

echo "Bringing up rest_server_deployment"
kubectl apply -f deployment/GKE/GKE_rest_server_service.yaml

echo "Bringing up rest_server_service"
kubectl apply -f deployment/GKE/GKE_splitter_deployment.yaml

echo "Bringing up chunker_deployment"
kubectl apply -f deployment/GKE/GKE_chunker_deployment.yaml

echo "Bringing up tts_deployment"
kubectl apply -f deployment/GKE/GKE_tts_deployment.yaml

echo "Bringing up audio_stitcher_deployment"
kubectl apply -f deployment/GKE/GKE_audio_stitcher_deployment.yaml

echo "GKE Deployment completed successfully."
