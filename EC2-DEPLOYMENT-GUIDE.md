# 🚀 EC2 Deployment Guide for Skyro backend-orders

## Step 1 — Launch an EC2 Instance

1. Open [AWS EC2 Console](https://console.aws.amazon.com/ec2)
2. Click **Launch Instance**
3. Settings:
   - **Name**: `skyro-backend`
   - **AMI**: Ubuntu Server 22.04 LTS (free tier eligible)
   - **Instance type**: `t3.micro` (free tier)
   - **Key pair**: Create new → download `.pem` file
   - **Security Group** (CRITICAL — must allow):
     | Type | Protocol | Port | Source |
     |---|---|---|---|
     | SSH | TCP | 22 | Your IP |
     | Custom TCP | TCP | **8000** | 0.0.0.0/0 (Anywhere) |
4. Click **Launch Instance**

> **Note the Public IPv4 address** from the EC2 dashboard — you'll need it!

---

## Step 2 — Copy Your Code to EC2

From your Windows machine (PowerShell):

```powershell
# Create a zip of just the backend-orders folder
Compress-Archive -Path "D:\Drone Projects\AreoDroneNew\Skyro\backend-orders" -DestinationPath "C:\temp\backend-orders.zip"

# Copy to EC2 (replace with your actual IP and key file path)
scp -i "C:\path\to\your-key.pem" "C:\temp\backend-orders.zip" ubuntu@<EC2_PUBLIC_IP>:/home/ubuntu/
```

Or use **WinSCP** or **FileZilla** with your `.pem` key to upload the `backend-orders` folder.

---

## Step 3 — SSH into EC2 and Deploy

```powershell
# SSH into the EC2 instance
ssh -i "C:\path\to\your-key.pem" ubuntu@<EC2_PUBLIC_IP>
```

Once inside:

```bash
# Unzip your code
cd /home/ubuntu
unzip backend-orders.zip
ls  # you should see the backend-orders folder

# Create .env file with your RDS credentials
cat > /home/ubuntu/backend-orders/.env << 'EOF'
DATABASE_URL=postgresql+asyncpg://skyro_admin:Skyro5172@skyro-db.cl4o2c2matz8.ap-south-1.rds.amazonaws.com:5432/skyro?sslmode=require
RAZORPAY_KEY_ID=rzp_test_placeholder
RAZORPAY_KEY_SECRET=placeholder
CORS_ORIGINS=*
EOF

# Install Docker
sudo apt-get update -y
sudo apt-get install -y docker.io
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ubuntu
# Log out and back in for group to apply
exit
```

SSH back in:

```bash
ssh -i "C:\path\to\your-key.pem" ubuntu@<EC2_PUBLIC_IP>

# Build and run the container
cd /home/ubuntu/backend-orders
docker build -t skyro-orders:latest .

docker run -d \
  --name skyro-orders \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file .env \
  skyro-orders:latest

# Verify it's running
docker ps
curl http://localhost:8000/api/restaurants
```

---

## Step 4 — Set the EC2 URL in the Android App

1. **Edit** `NetworkConfig.kt` in the app:
   ```
   D:\Drone Projects\AreoDroneNew\Skyro\skyro_app\app\src\main\java\com\example\data\NetworkConfig.kt
   ```
   Change:
   ```kotlin
   const val DEFAULT_BASE_URL = "http://YOUR_EC2_IP:8000"
   ```
   To (example):
   ```kotlin
   const val DEFAULT_BASE_URL = "http://13.235.120.45:8000"
   ```

2. **Rebuild the APK** in Android Studio: `Build → Build Bundle(s)/APK(s) → Build APK(s)`

---

## Step 5 — Test the Connection

From any browser or Postman:
```
http://<EC2_PUBLIC_IP>:8000/api/restaurants
http://<EC2_PUBLIC_IP>:8000/api/menu-items
http://<EC2_PUBLIC_IP>:8000/api/locations
```

---

## ⚡ Quick Alternative — Test Locally First

If you want to test the Android app against your local machine first (before EC2):

1. Find your PC's local IP: `ipconfig` → look for `IPv4 Address` (e.g., `192.168.1.5`)
2. Run the backend locally:
   ```powershell
   cd "D:\Drone Projects\AreoDroneNew\Skyro\backend-orders"
   pip install -r requirements.txt
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
3. Set `DEFAULT_BASE_URL = "http://192.168.1.5:8000"` in `NetworkConfig.kt`
4. Connect your Android phone to the **same WiFi** as your PC

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Connection refused` on port 8000 | Check EC2 Security Group — port 8000 must be open |
| App shows "offline fallback" | Check that `DEFAULT_BASE_URL` in `NetworkConfig.kt` is updated |
| `cleartext traffic not permitted` | `usesCleartextTraffic=true` is already set in AndroidManifest ✅ |
| Database not seeded | Run `python db/migrate.py` with the RDS URL to seed restaurants/menus |
