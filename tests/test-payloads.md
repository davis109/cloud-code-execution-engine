# Example test payloads for manual testing

## Python Examples

### Hello World
```json
{
  "language": "python",
  "code": "print('Hello from distributed executor!')"
}
```

### Math Calculation
```json
{
  "language": "python",
  "code": "import math\nprint(f'Pi = {math.pi}')\nprint(f'Square root of 16 = {math.sqrt(16)}')"
}
```

### List Comprehension
```json
{
  "language": "python",
  "code": "squares = [x**2 for x in range(10)]\nprint(squares)"
}
```

### JSON Parsing
```json
{
  "language": "python",
  "code": "import json\ndata = {'name': 'test', 'value': 123}\nprint(json.dumps(data, indent=2))"
}
```

---

## JavaScript Examples

### Console Log
```json
{
  "language": "javascript",
  "code": "console.log('Hello from Node.js!');"
}
```

### Math Operations
```json
{
  "language": "javascript",
  "code": "const result = Array.from({length: 10}, (_, i) => i * 2);\nconsole.log(result);"
}
```

### String Manipulation
```json
{
  "language": "javascript",
  "code": "const text = 'hello world';\nconsole.log(text.toUpperCase());\nconsole.log(text.split(' ').reverse().join(' '));"
}
```

---

## Ruby Examples

### Hello World
```json
{
  "language": "ruby",
  "code": "puts 'Hello from Ruby!'"
}
```

### Array Operations
```json
{
  "language": "ruby",
  "code": "numbers = (1..10).to_a\nsquares = numbers.map { |n| n ** 2 }\nputs squares.join(', ')"
}
```

---

## Go Examples

### Hello World
```json
{
  "language": "go",
  "code": "package main\nimport \"fmt\"\nfunc main() {\n\tfmt.Println(\"Hello from Go!\")\n}"
}
```

---

## Security Test Cases

### Infinite Loop (Timeout Test)
```json
{
  "language": "python",
  "code": "while True: pass",
  "timeout": 3
}
```
**Expected:** Status = TIMEOUT, error = "Execution exceeded 3s limit"

### Fork Bomb (Process Limit Test)
```json
{
  "language": "python",
  "code": "import os\nwhile True: os.fork()"
}
```
**Expected:** Status = ERROR, error mentions process limit

### Memory Bomb (Memory Limit Test)
```json
{
  "language": "python",
  "code": "x = [0] * (10**8)"
}
```
**Expected:** Status = ERROR, OOM killed

### Network Access Attempt (Network Isolation Test)
```json
{
  "language": "python",
  "code": "import urllib.request\nurllib.request.urlopen('https://www.google.com')"
}
```
**Expected:** Status = ERROR, network unreachable

### File System Write Attempt (Read-only FS Test)
```json
{
  "language": "python",
  "code": "with open('/tmp/test.txt', 'w') as f:\n\tf.write('test')"
}
```
**Expected:** Status = ERROR, read-only file system

---

## Error Handling Test Cases

### Syntax Error
```json
{
  "language": "python",
  "code": "print(invalid syntax"
}
```
**Expected:** Status = ERROR, stderr contains syntax error

### Runtime Error
```json
{
  "language": "python",
  "code": "print(1/0)"
}
```
**Expected:** Status = ERROR, stderr contains "ZeroDivisionError"

### Import Error
```json
{
  "language": "python",
  "code": "import nonexistent_module"
}
```
**Expected:** Status = ERROR, stderr contains "ModuleNotFoundError"

---

## Curl Commands

### Submit Job
```bash
curl -X POST https://YOUR_API.execute-api.us-east-1.amazonaws.com/prod/execute \
  -H "Content-Type: application/json" \
  -d @- << EOF
{
  "language": "python",
  "code": "print('Hello World!')"
}
EOF
```

### Check Status
```bash
JOB_ID="550e8400-e29b-41d4-a716-446655440000"
curl https://YOUR_API.execute-api.us-east-1.amazonaws.com/prod/status/$JOB_ID
```

### Submit and Poll
```bash
# Submit
RESPONSE=$(curl -s -X POST $API_ENDPOINT/execute \
  -H "Content-Type: application/json" \
  -d '{"language": "python", "code": "print(123)"}')

# Extract job_id
JOB_ID=$(echo $RESPONSE | jq -r '.job_id')

# Wait and check
sleep 3
curl $API_ENDPOINT/status/$JOB_ID | jq
```
