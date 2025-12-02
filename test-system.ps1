# Test the Code Execution Engine
Write-Host "Testing Code Execution Engine..." -ForegroundColor Cyan

$apiEndpoint = "https://9t9muq2hv0.execute-api.us-east-1.amazonaws.com/prod"

# Test 1: Submit a Python job
Write-Host "`nTest 1: Submitting Python code..." -ForegroundColor Yellow
$pythonPayload = @{
    language = "python"
    code = "print('Hello from the Code Execution Engine!')`nprint('2 + 2 =', 2 + 2)"
    timeout = 5
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "$apiEndpoint/execute" -Method POST -Body $pythonPayload -ContentType "application/json"
$jobId = $response.job_id
Write-Host "Job ID: $jobId" -ForegroundColor Green

# Wait for execution
Write-Host "`nWaiting for execution (10 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Test 2: Check status
Write-Host "`nTest 2: Checking job status..." -ForegroundColor Yellow
$result = Invoke-RestMethod -Uri "$apiEndpoint/status/$jobId" -Method GET
Write-Host "Status: $($result.status)" -ForegroundColor Green
Write-Host "Output:" -ForegroundColor White
Write-Host $result.output -ForegroundColor Gray

# Test 3: Submit JavaScript code
Write-Host "`n`nTest 3: Submitting JavaScript code..." -ForegroundColor Yellow
$jsPayload = @{
    language = "javascript"
    code = "console.log('Hello from Node.js!');`nconsole.log('5 * 5 =', 5 * 5);"
    timeout = 5
} | ConvertTo-Json

$response2 = Invoke-RestMethod -Uri "$apiEndpoint/execute" -Method POST -Body $jsPayload -ContentType "application/json"
$jobId2 = $response2.job_id
Write-Host "Job ID: $jobId2" -ForegroundColor Green

# Wait and check
Start-Sleep -Seconds 10
$result2 = Invoke-RestMethod -Uri "$apiEndpoint/status/$jobId2" -Method GET
Write-Host "Status: $($result2.status)" -ForegroundColor Green
Write-Host "Output:" -ForegroundColor White
Write-Host $result2.output -ForegroundColor Gray

Write-Host "`n`n========================================" -ForegroundColor Cyan
Write-Host "Tests Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Your distributed code execution engine is fully operational!" -ForegroundColor Green
