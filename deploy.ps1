# Deployment Script for Code Execution Engine
# Run this in PowerShell

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Code Execution Engine - Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
Write-Host "Checking prerequisites..." -ForegroundColor Yellow

# Check AWS CLI
try {
    $awsVersion = aws --version 2>&1
    Write-Host "✓ AWS CLI installed: $awsVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ AWS CLI not found. Please install from: https://aws.amazon.com/cli/" -ForegroundColor Red
    exit 1
}

# Check AWS credentials
try {
    $identity = aws sts get-caller-identity 2>&1 | ConvertFrom-Json
    Write-Host "✓ AWS credentials configured" -ForegroundColor Green
    Write-Host "  Account ID: $($identity.Account)" -ForegroundColor Gray
    Write-Host "  User: $($identity.Arn)" -ForegroundColor Gray
} catch {
    Write-Host "✗ AWS credentials not configured. Run 'aws configure'" -ForegroundColor Red
    exit 1
}

# Get region
$region = aws configure get region
if (-not $region) {
    $region = "us-east-1"
    Write-Host "! No region configured, using default: $region" -ForegroundColor Yellow
} else {
    Write-Host "✓ Region: $region" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deployment Options" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Full deployment (CloudFormation stack)" -ForegroundColor White
Write-Host "2. Test existing deployment" -ForegroundColor White
Write-Host "3. Check costs and usage" -ForegroundColor White
Write-Host "4. Cleanup/Delete stack" -ForegroundColor White
Write-Host "5. View documentation" -ForegroundColor White
Write-Host "6. Exit" -ForegroundColor White
Write-Host ""

$choice = Read-Host "Select option (1-6)"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "Full Deployment" -ForegroundColor Cyan
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host ""
        
        # Check for EC2 key pair
        Write-Host "Checking for EC2 key pairs..." -ForegroundColor Yellow
        $keyPairs = aws ec2 describe-key-pairs --region $region 2>&1 | ConvertFrom-Json
        
        if ($keyPairs.KeyPairs.Count -eq 0) {
            Write-Host "! No key pairs found. Creating one..." -ForegroundColor Yellow
            $keyName = "code-executor-key"
            
            $keyMaterial = aws ec2 create-key-pair --key-name $keyName --region $region --query 'KeyMaterial' --output text
            $keyMaterial | Out-File -FilePath "$keyName.pem" -Encoding ASCII
            
            Write-Host "✓ Created key pair: $keyName" -ForegroundColor Green
            Write-Host "  Saved to: $keyName.pem" -ForegroundColor Gray
        } else {
            Write-Host "Available key pairs:" -ForegroundColor White
            for ($i = 0; $i -lt $keyPairs.KeyPairs.Count; $i++) {
                Write-Host "  $($i + 1). $($keyPairs.KeyPairs[$i].KeyName)" -ForegroundColor Gray
            }
            
            $keyChoice = Read-Host "Select key pair number (or press Enter to create new)"
            
            if ($keyChoice -and [int]$keyChoice -le $keyPairs.KeyPairs.Count) {
                $keyName = $keyPairs.KeyPairs[[int]$keyChoice - 1].KeyName
                Write-Host "✓ Using existing key: $keyName" -ForegroundColor Green
            } else {
                $keyName = "code-executor-key-" + (Get-Date -Format "yyyyMMdd-HHmmss")
                $keyMaterial = aws ec2 create-key-pair --key-name $keyName --region $region --query 'KeyMaterial' --output text
                $keyMaterial | Out-File -FilePath "$keyName.pem" -Encoding ASCII
                Write-Host "✓ Created key pair: $keyName" -ForegroundColor Green
            }
        }
        
        Write-Host ""
        Write-Host "⚠️  IMPORTANT: Cost Warning" -ForegroundColor Yellow
        Write-Host "This will create AWS resources. Ensure you:" -ForegroundColor Yellow
        Write-Host "  1. Are within AWS Free Tier limits" -ForegroundColor Yellow
        Write-Host "  2. Have set a billing alarm" -ForegroundColor Yellow
        Write-Host "  3. Understand the cost implications" -ForegroundColor Yellow
        Write-Host ""
        
        $confirm = Read-Host "Continue with deployment? (yes/no)"
        
        if ($confirm -ne "yes") {
            Write-Host "Deployment cancelled." -ForegroundColor Yellow
            exit 0
        }
        
        Write-Host ""
        Write-Host "Deploying CloudFormation stack..." -ForegroundColor Yellow
        
        $stackName = "code-executor-stack"
        
        aws cloudformation create-stack `
            --stack-name $stackName `
            --template-body file://infrastructure/cloudformation-template.yaml `
            --parameters ParameterKey=KeyPairName,ParameterValue=$keyName `
            --capabilities CAPABILITY_NAMED_IAM `
            --region $region
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Stack creation initiated!" -ForegroundColor Green
            Write-Host ""
            Write-Host "Waiting for stack creation to complete (this may take 5-10 minutes)..." -ForegroundColor Yellow
            Write-Host "You can monitor progress in AWS Console: CloudFormation" -ForegroundColor Gray
            Write-Host ""
            
            aws cloudformation wait stack-create-complete --stack-name $stackName --region $region
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host ""
                Write-Host "✓ Stack created successfully!" -ForegroundColor Green
                Write-Host ""
                
                # Get outputs
                $outputs = aws cloudformation describe-stacks --stack-name $stackName --region $region --query 'Stacks[0].Outputs' | ConvertFrom-Json
                
                Write-Host "Stack Outputs:" -ForegroundColor Cyan
                foreach ($output in $outputs) {
                    Write-Host "  $($output.OutputKey): $($output.OutputValue)" -ForegroundColor White
                }
                
                Write-Host ""
                Write-Host "Next Steps:" -ForegroundColor Cyan
                Write-Host "1. Deploy worker code to EC2 (see DEPLOYMENT.md)" -ForegroundColor White
                Write-Host "2. Deploy Lambda functions (see DEPLOYMENT.md)" -ForegroundColor White
                Write-Host "3. Test the API" -ForegroundColor White
            } else {
                Write-Host "✗ Stack creation failed. Check AWS Console for details." -ForegroundColor Red
            }
        } else {
            Write-Host "✗ Failed to create stack. Check error above." -ForegroundColor Red
        }
    }
    
    "2" {
        Write-Host ""
        Write-Host "Testing existing deployment..." -ForegroundColor Yellow
        
        $stackName = Read-Host "Enter stack name (default: code-executor-stack)"
        if (-not $stackName) { $stackName = "code-executor-stack" }
        
        try {
            $stack = aws cloudformation describe-stacks --stack-name $stackName --region $region 2>&1 | ConvertFrom-Json
            
            $apiEndpoint = ($stack.Stacks[0].Outputs | Where-Object { $_.OutputKey -eq "ApiEndpoint" }).OutputValue
            
            if ($apiEndpoint) {
                Write-Host "✓ Found API Endpoint: $apiEndpoint" -ForegroundColor Green
                Write-Host ""
                Write-Host "Testing API..." -ForegroundColor Yellow
                
                $testPayload = @{
                    language = "python"
                    code = "print('Hello from PowerShell deployment!')"
                } | ConvertTo-Json
                
                try {
                    $response = Invoke-RestMethod -Uri "$apiEndpoint/execute" -Method Post -Body $testPayload -ContentType "application/json"
                    
                    Write-Host "✓ Job submitted!" -ForegroundColor Green
                    Write-Host "  Job ID: $($response.job_id)" -ForegroundColor Gray
                    
                    Write-Host ""
                    Write-Host "Waiting 3 seconds for execution..." -ForegroundColor Yellow
                    Start-Sleep -Seconds 3
                    
                    $statusResponse = Invoke-RestMethod -Uri "$apiEndpoint/status/$($response.job_id)" -Method Get
                    
                    Write-Host ""
                    Write-Host "Result:" -ForegroundColor Cyan
                    Write-Host "  Status: $($statusResponse.status)" -ForegroundColor White
                    Write-Host "  Output: $($statusResponse.output)" -ForegroundColor White
                    Write-Host "  Execution Time: $($statusResponse.execution_time_ms)ms" -ForegroundColor White
                    
                    if ($statusResponse.status -eq "SUCCESS") {
                        Write-Host ""
                        Write-Host "✓ Deployment is working correctly!" -ForegroundColor Green
                    }
                } catch {
                    Write-Host "✗ API test failed: $_" -ForegroundColor Red
                }
            } else {
                Write-Host "✗ API Endpoint not found in stack outputs" -ForegroundColor Red
            }
        } catch {
            Write-Host "✗ Stack not found: $stackName" -ForegroundColor Red
        }
    }
    
    "3" {
        Write-Host ""
        Write-Host "Checking AWS costs and usage..." -ForegroundColor Yellow
        Write-Host ""
        
        $startDate = (Get-Date).AddDays(-30).ToString("yyyy-MM-dd")
        $endDate = (Get-Date).ToString("yyyy-MM-dd")
        
        try {
            $costs = aws ce get-cost-and-usage `
                --time-period Start=$startDate,End=$endDate `
                --granularity MONTHLY `
                --metrics UnblendedCost `
                --region us-east-1 | ConvertFrom-Json
            
            Write-Host "Monthly Cost Summary:" -ForegroundColor Cyan
            foreach ($result in $costs.ResultsByTime) {
                $amount = [math]::Round([decimal]$result.Total.UnblendedCost.Amount, 2)
                Write-Host "  Period: $($result.TimePeriod.Start) to $($result.TimePeriod.End)" -ForegroundColor White
                Write-Host "  Cost: $$amount USD" -ForegroundColor White
            }
            
            Write-Host ""
            Write-Host "Note: Free Tier services show as `$0.00" -ForegroundColor Gray
        } catch {
            Write-Host "✗ Could not retrieve cost data. Ensure Cost Explorer is enabled." -ForegroundColor Red
        }
    }
    
    "4" {
        Write-Host ""
        Write-Host "⚠️  WARNING: This will delete all resources!" -ForegroundColor Yellow
        Write-Host ""
        
        $stackName = Read-Host "Enter stack name to delete (default: code-executor-stack)"
        if (-not $stackName) { $stackName = "code-executor-stack" }
        
        $confirm = Read-Host "Type 'DELETE' to confirm deletion"
        
        if ($confirm -eq "DELETE") {
            Write-Host ""
            Write-Host "Deleting stack..." -ForegroundColor Yellow
            
            aws cloudformation delete-stack --stack-name $stackName --region $region
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "✓ Deletion initiated. Waiting for completion..." -ForegroundColor Green
                
                aws cloudformation wait stack-delete-complete --stack-name $stackName --region $region
                
                Write-Host "✓ Stack deleted successfully!" -ForegroundColor Green
            } else {
                Write-Host "✗ Failed to delete stack" -ForegroundColor Red
            }
        } else {
            Write-Host "Deletion cancelled." -ForegroundColor Yellow
        }
    }
    
    "5" {
        Write-Host ""
        Write-Host "Opening documentation..." -ForegroundColor Yellow
        Start-Process "GETTING_STARTED.md"
    }
    
    "6" {
        Write-Host "Exiting..." -ForegroundColor Gray
        exit 0
    }
    
    default {
        Write-Host "Invalid option. Exiting." -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "For detailed instructions, see:" -ForegroundColor White
Write-Host "  - GETTING_STARTED.md" -ForegroundColor Gray
Write-Host "  - DEPLOYMENT.md" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
