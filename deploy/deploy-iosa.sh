#!/bin/bash
# ============================================================================
# IOSA Document Parser - Deployment Script
# ============================================================================
#
# This script deploys the IOSA parser on a Scaleway Ubuntu 22.04 GPU server.
#
# Usage:
#   ./deploy-iosa.sh [OPTIONS]
#
# Options:
#   --cpu         Deploy CPU-only version
#   --dev         Development mode with auto-reload
#   --with-cache  Enable Redis caching
#   --with-proxy  Enable Nginx reverse proxy
#   --build       Force rebuild Docker images
#   --clean       Clean up and start fresh
#
# Requirements:
#   - Docker & Docker Compose
#   - NVIDIA Container Toolkit (for GPU)
#   - Git
#
# ============================================================================

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.iosa.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
USE_GPU=true
DEV_MODE=false
WITH_CACHE=false
WITH_PROXY=false
FORCE_BUILD=false
CLEAN=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --cpu)
            USE_GPU=false
            shift
            ;;
        --dev)
            DEV_MODE=true
            shift
            ;;
        --with-cache)
            WITH_CACHE=true
            shift
            ;;
        --with-proxy)
            WITH_PROXY=true
            shift
            ;;
        --build)
            FORCE_BUILD=true
            shift
            ;;
        --clean)
            CLEAN=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --cpu         Deploy CPU-only version"
            echo "  --dev         Development mode with auto-reload"
            echo "  --with-cache  Enable Redis caching"
            echo "  --with-proxy  Enable Nginx reverse proxy"
            echo "  --build       Force rebuild Docker images"
            echo "  --clean       Clean up and start fresh"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose."
        exit 1
    fi

    log_success "Docker is available"
}

check_gpu() {
    if [ "$USE_GPU" = true ]; then
        if ! nvidia-smi &> /dev/null; then
            log_warning "NVIDIA GPU not detected. Switching to CPU mode."
            USE_GPU=false
        else
            if ! docker run --rm --gpus all nvidia/cuda:12.1-base-ubuntu22.04 nvidia-smi &> /dev/null; then
                log_warning "NVIDIA Container Toolkit not working. Switching to CPU mode."
                USE_GPU=false
            else
                log_success "GPU support is available"
                nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
            fi
        fi
    fi
}

install_nvidia_toolkit() {
    log_info "Installing NVIDIA Container Toolkit..."

    # Add NVIDIA repository
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

    sudo apt-get update
    sudo apt-get install -y nvidia-container-toolkit
    sudo nvidia-ctk runtime configure --runtime=docker
    sudo systemctl restart docker

    log_success "NVIDIA Container Toolkit installed"
}

setup_environment() {
    log_info "Setting up environment..."

    # Create necessary directories
    mkdir -p "$SCRIPT_DIR/models"
    mkdir -p "$SCRIPT_DIR/ssl"
    mkdir -p "$PROJECT_DIR/data"
    mkdir -p "$PROJECT_DIR/output"

    # Create .env file if not exists
    if [ ! -f "$SCRIPT_DIR/.env" ]; then
        cat > "$SCRIPT_DIR/.env" << EOF
# IOSA Parser Environment Variables
# ==================================

# HuggingFace Token (optional, for gated models)
HF_TOKEN=

# API Configuration
IOSA_HOST=0.0.0.0
IOSA_PORT=8000
IOSA_WORKERS=1

# Parser Configuration
IOSA_DEVICE=$([ "$USE_GPU" = true ] && echo "cuda" || echo "cpu")
IOSA_BATCH_SIZE=$([ "$USE_GPU" = true ] && echo "4" || echo "1")
IOSA_TABLE_MODE=hybrid
IOSA_ENABLE_OCR=true

# VLM Model
IOSA_VLM_MODEL=pgadet-wq/granite-docling-258M
EOF
        log_info "Created .env file. Please edit it if needed."
    fi

    log_success "Environment setup complete"
}

build_image() {
    log_info "Building Docker image..."

    cd "$PROJECT_DIR"

    if [ "$FORCE_BUILD" = true ]; then
        docker build --no-cache -f deploy/Dockerfile.iosa -t iosa-parser:latest .
    else
        docker build -f deploy/Dockerfile.iosa -t iosa-parser:latest .
    fi

    log_success "Docker image built successfully"
}

deploy_service() {
    log_info "Deploying IOSA Parser service..."

    cd "$SCRIPT_DIR"

    # Build compose command
    COMPOSE_CMD="docker compose -f docker-compose.iosa.yml"
    PROFILES=""

    if [ "$USE_GPU" = false ]; then
        PROFILES="$PROFILES --profile cpu"
    fi

    if [ "$WITH_CACHE" = true ]; then
        PROFILES="$PROFILES --profile with-cache"
    fi

    if [ "$WITH_PROXY" = true ]; then
        PROFILES="$PROFILES --profile with-proxy"
    fi

    # Stop existing services
    $COMPOSE_CMD down --remove-orphans 2>/dev/null || true

    # Start services
    if [ -n "$PROFILES" ]; then
        $COMPOSE_CMD $PROFILES up -d
    else
        $COMPOSE_CMD up -d
    fi

    log_success "Service deployed successfully"
}

run_dev_mode() {
    log_info "Starting in development mode..."

    cd "$PROJECT_DIR"

    # Install dependencies
    pip install -e ".[vlm]"
    pip install fastapi uvicorn python-multipart

    # Run with reload
    uvicorn docling.iosa.api:app --host 0.0.0.0 --port 8000 --reload
}

cleanup() {
    log_info "Cleaning up..."

    cd "$SCRIPT_DIR"

    docker compose -f docker-compose.iosa.yml down -v --remove-orphans 2>/dev/null || true
    docker rmi iosa-parser:latest 2>/dev/null || true

    log_success "Cleanup complete"
}

show_status() {
    echo ""
    echo "=============================================="
    echo "IOSA Parser Deployment Status"
    echo "=============================================="
    echo ""

    docker ps --filter "name=iosa" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

    echo ""
    echo "Service URL: http://localhost:8000"
    echo "API Docs:    http://localhost:8000/docs"
    echo "Health:      http://localhost:8000/health"
    echo ""

    # Wait for service to be ready
    log_info "Waiting for service to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            log_success "Service is ready!"
            break
        fi
        sleep 2
    done
}

# Main execution
main() {
    echo ""
    echo "=============================================="
    echo "IOSA Document Parser - Deployment"
    echo "=============================================="
    echo ""

    # Clean up if requested
    if [ "$CLEAN" = true ]; then
        cleanup
    fi

    # Check prerequisites
    check_docker
    check_gpu

    # Setup environment
    setup_environment

    # Development mode
    if [ "$DEV_MODE" = true ]; then
        run_dev_mode
        exit 0
    fi

    # Build and deploy
    build_image
    deploy_service
    show_status

    echo ""
    log_success "Deployment complete!"
    echo ""
    echo "Quick test:"
    echo "  curl -X POST http://localhost:8000/parse \\"
    echo "    -F 'file=@your_document.pdf'"
    echo ""
}

main
