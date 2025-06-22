#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Building nginx Docker image...${NC}"

# Build the Docker image
docker build -t nginx-proxy .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Docker image built successfully!${NC}"
else
    echo -e "${RED}❌ Failed to build Docker image${NC}"
    exit 1
fi

echo -e "${YELLOW}Starting nginx container...${NC}"

# Stop and remove existing container if it exists
docker stop nginx-proxy-container 2>/dev/null
docker rm nginx-proxy-container 2>/dev/null

# Run the container with port mapping to access host services
docker run -d \
    --name nginx-proxy-container \
    -p 80:80 \
    nginx-proxy

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ nginx container started successfully!${NC}"
    echo -e "${GREEN}🚀 nginx is now running on http://localhost:80${NC}"
    echo -e "${YELLOW}📋 Container logs:${NC}"
    docker logs nginx-proxy-container
    echo -e "${YELLOW}💡 To view logs: docker logs -f nginx-proxy-container${NC}"
    echo -e "${YELLOW}🛑 To stop: docker stop nginx-proxy-container${NC}"
else
    echo -e "${RED}❌ Failed to start nginx container${NC}"
    exit 1
fi 