#!/bin/bash
set -e

echo 'Setting up Code Execution Worker...'

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

echo 'Starting service...'
sudo systemctl daemon-reload
sudo systemctl enable code-executor
sudo systemctl restart code-executor

sleep 3
echo 'Service status:'
sudo systemctl status code-executor --no-pager -l

echo ''
echo 'Worker deployed successfully!'