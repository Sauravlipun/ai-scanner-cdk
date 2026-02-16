import json
import subprocess
import tempfile
import os
import sys

def lambda_handler(event, context):
    """
    Execute generated exploit script in isolated sandbox environment
    Runs in VPC with NO internet access - completely isolated
    
    Expected event format:
    {
        "script": "print('testing...')",
        "scan_id": "12345",
        "target_url": "http://10.0.1.45:8080"
    }
    """
    
    try:
        # Extract script from event
        body = json.loads(event.get('body', '{}')) if isinstance(event.get('body'), str) else event
        script = body.get('script', '')
        scan_id = body.get('scan_id', 'unknown')
        target_url = body.get('target_url', '')
        
        if not script:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing script'})
            }
        
        # Create temporary file for the script
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(script)
            script_path = f.name
        
        # Set environment variables for the script
        env = os.environ.copy()
        env['TARGET_URL'] = target_url
        env['SCAN_ID'] = scan_id
        
        # Execute script in isolated subprocess
        # Note: This Lambda has no internet access - network calls will fail
        result = subprocess.run(
            [sys.executable, script_path],
            env=env,
            capture_output=True,
            text=True,
            timeout=240  # 4 minutes max
        )
        
        # Clean up
        os.unlink(script_path)
        
        # Determine if vulnerable based on exit code
        is_vulnerable = result.returncode == 0
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'scan_id': scan_id,
                'vulnerable': is_vulnerable,
                'exit_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'script_executed': True
            })
        }
        
    except subprocess.TimeoutExpired:
        return {
            'statusCode': 408,
            'body': json.dumps({
                'error': 'Script execution timeout',
                'vulnerable': False
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'vulnerable': False
            })
        }
