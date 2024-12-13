# Makefile

# Default version if not specified
VERSION ?= latest

# Define services and their respective Dockerfiles
SERVICES := rest_server tts audio_stitcher chunker splitter event_tracker
DOCKERFILES := $(addprefix src/Dockerfile_, $(SERVICES))

# Define the Docker Hub username
DOCKER_USERNAME := pratikbhirud

# Define a rule to build and push all services
.PHONY: all
all: $(SERVICES)

# Generic rule to build and push each service
$(SERVICES):
	@echo "Building and pushing Docker image for $@..."
	docker build -t $(DOCKER_USERNAME)/$@:$(VERSION) -f src/Dockerfile_$@ .
	docker push $(DOCKER_USERNAME)/$@:$(VERSION)

# Clean target (optional, if needed for cleanup purposes)
.PHONY: clean
clean:
	@echo "Cleaning up Docker images for services..."
	@for service in $(SERVICES); do \
		docker rmi $(DOCKER_USERNAME)/$$service:$(VERSION) || true; \
	done
