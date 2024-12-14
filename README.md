# NarrateNow Deployment

This repository contains the deployment script and configuration files to set up the **NarrateNow** audiobook generation platform on a Kubernetes cluster. The platform leverages **RabbitMQ**, **Redis**, and various backend microservices to create chapter-wise audiobooks.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [Step 1: Clone the Repository](#step-1-clone-the-repository)
  - [Step 2: Make the Script Executable](#step-2-make-the-script-executable)
  - [Step 3: Run the Deployment Script](#step-3-run-the-deployment-script)

## Overview

**NarrateNow** is a cloud-based service designed to convert EPUB files into chapter-wise audiobooks. This deployment sets up the microservice-based architecture, including:

- **Message Queueing** with RabbitMQ
- **Status Tracking** with Redis
- **Backend Microservices** for splitting, chunking, text-to-speech conversion, and audio stitching

## Features

- **Automated Deployment**: Single script to deploy all services.
- **Scalable Infrastructure**: Built using Kubernetes for container orchestration.
- **Cloud-Ready**: Easily deployable on Google Kubernetes Engine (GKE) or any Kubernetes cluster.
- **Modular Design**: Microservice architecture for easy maintenance and scaling.

## Prerequisites

Ensure the following are installed and configured:

1. **Kubernetes Cluster**: A working Kubernetes cluster (e.g., Minikube, GKE, EKS).
2. **kubectl**: Command-line tool to interact with the Kubernetes cluster.
3. **Helm**: Installed for RabbitMQ deployment.
4. **Deployment Files**: All necessary Kubernetes manifests are located in the `deployment/` directory.

## Installation

### Step 1: Clone the Repository

Clone this repository to your local machine:
```bash
git clone <repository-url>
cd <repository-folder>
```
### Step 2: Make the Script Executable
Ensure the deployment script has the necessary permissions:

```bash
chmod +x deploy.sh
```
### Step 3: Run the Deployment Script
Deploy the services with a single command:
```
bash
./deploy_services.sh
```
Usage
1. Verifying the Deployment
2. After the script runs, verify that all services are running:
