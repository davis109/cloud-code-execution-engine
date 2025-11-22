# Deploy Worker to EC2
Write-Host "Deploying Code Execution Worker..." -ForegroundColor Cyan

$workerIP = "54.85.54.85"
$keyFile = "code-executor-key.pem"

# Copy files to EC2
Write-Host "`nStep 1: Copying files to EC2..." -ForegroundColor Yellow
scp -i $keyFile -o StrictHostKeyChecking=no worker/executor.py ec2-user@${workerIP}:/tmp/
scp -i $keyFile -o StrictHostKeyChecking=no worker/requirements.txt ec2-user@${workerIP}:/tmp/
scp -i $keyFile -o StrictHostKeyChecking=no worker/code-executor.service ec2-user@${workerIP}:/tmp/

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to copy files" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Files copied successfully" -ForegroundColor Green

# Configure and start the service
Write-Host "`nStep 2: Setting up worker service..." -ForegroundColor Yellow

ssh -i $keyFile -o StrictHostKeyChecking=no ec2-user@$workerIP @"
sudo mkdir -p /opt/code-executor
sudo mv /tmp/executor.py /opt/code-executor/
sudo mv /tmp/requirements.txt /opt/code-executor/
sudo mv /tmp/code-executor.service /etc/systemd/system/
sudo chmod +x /opt/code-executor/executor.py
echo 'Installing Python dependencies...'
sudo pip3 install -q -r /opt/code-executor/requirements.txt
echo 'Pre-pulling Docker images...'
sudo docker pull python:3.11-alpine
sudo docker pull node:18-alpine  
sudo docker pull ruby:3.2-alpine
sudo docker pull golang:1.21-alpine
sudo systemctl daemon-reload
sudo systemctl enable code-executor
sudo systemctl start code-executor
sleep 2
sudo systemctl status code-executor --no-pager
"@

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[OK] Worker service deployed and started!" -ForegroundColor Green
    Write-Host "`nCheck logs with:" -ForegroundColor White
    Write-Host "  ssh -i $keyFile ec2-user@$workerIP" -ForegroundColor Gray
    Write-Host "  sudo journalctl -u code-executor -f" -ForegroundColor Gray
} else {
    Write-Host "`n[ERROR] Failed to setup worker service" -ForegroundColor Red
    exit 1
}
