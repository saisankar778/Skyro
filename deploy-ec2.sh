#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Skyro — EC2 Deployment Script for backend-orders
# Run this ON the EC2 instance after SSH-ing in.
# Usage:
#   chmod +x deploy-ec2.sh
#   ./deploy-ec2.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e

echo "============================="
echo "  SKYRO — EC2 Deployment"
echo "============================="

# 1. Install Docker if not already installed
if ! command -v docker &> /dev/null; then
    echo "[1/6] Installing Docker..."
    sudo apt-get update -y
    sudo apt-get install -y ca-certificates curl gnupg
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker $USER
    echo "[1/6] Docker installed."
else
    echo "[1/6] Docker already installed. Skipping."
fi

# 2. Clone / pull latest code
if [ -d "/home/ubuntu/skyro" ]; then
    echo "[2/6] Pulling latest code..."
    cd /home/ubuntu/skyro
    git pull
else
    echo "[2/6] Cloning repo..."
    # Replace with your actual git repo URL if using git
    # git clone https://github.com/YOUR_USER/skyro.git /home/ubuntu/skyro
    echo "  NOTE: Copy your code to /home/ubuntu/skyro manually or via scp/git."
    mkdir -p /home/ubuntu/skyro
fi

cd /home/ubuntu/skyro

# 3. Write .env for backend-orders (uses your existing RDS)
echo "[3/6] Writing backend-orders environment..."
cat > backend-orders/.env << 'EOF'
DATABASE_URL=postgresql+asyncpg://skyro_admin:Skyro5172@skyro-db.cl4o2c2matz8.ap-south-1.rds.amazonaws.com:5432/skyro?sslmode=require
RAZORPAY_KEY_ID=rzp_test_placeholder
RAZORPAY_KEY_SECRET=placeholder
CORS_ORIGINS=*
EOF

# 4. Build & run the backend-orders container
echo "[4/6] Building Docker image for backend-orders..."
docker build -t skyro-orders:latest ./backend-orders

echo "[5/6] Stopping any existing container..."
docker stop skyro-orders 2>/dev/null || true
docker rm skyro-orders 2>/dev/null || true

echo "[6/6] Starting backend-orders container on port 8000..."
docker run -d \
  --name skyro-orders \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file backend-orders/.env \
  -e CORS_ORIGINS="*" \
  skyro-orders:latest

echo ""
echo "✅ Deployment complete!"
echo ""
echo "The backend-orders service is running on port 8000."
echo "Test it with:"
echo "  curl http://localhost:8000/api/restaurants"
echo ""
echo "Your EC2 PUBLIC IP is:"
curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "  (Run: curl http://169.254.169.254/latest/meta-data/public-ipv4)"
echo ""
echo "Android base URL should be: http://<YOUR_PUBLIC_IP>:8000"
