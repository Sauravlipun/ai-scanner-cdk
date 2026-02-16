import json
import boto3
import os
from openai import OpenAI

secrets_client = boto3.client('secretsmanager')

def get_openai_key(secret_arn):
    """Retrieve OpenAI API key from Secrets Manager"""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_arn)
        secret = json.loads(response['SecretString'])
        return secret.get('OPENAI_API_KEY')
    except Exception as e:
        print(f"Error retrieving secret: {str(e)}")
        raise

def lambda_handler(event, context):
    """
    Generate exploit validation script using OpenAI
    
    Expected event format:
    {
        "vulnerability": "SQL injection in login endpoint",
        "target_url": "http://example.com",
        "scan_id": "12345"
    }
    """
    try:
        # Parse input
        body = json.loads(event.get('body', '{}')) if isinstance(event.get('body'), str) else event
        vulnerability = body.get('vulnerability', '')
        target_url = body.get('target_url', '')
        
        if not vulnerability:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing vulnerability description'})
            }
        
        # Get OpenAI API key from Secrets Manager
        secret_arn = os.environ.get('OPENAI_SECRET_ARN')
        api_key = get_openai_key(secret_arn)
        
        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)
        
        # Generate exploit script
        model = os.environ.get('MODEL', 'gpt-4')
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system", 
                    "content": """You are a security testing assistant. Generate a Python script 
                    to validate if a vulnerability exists. The script should:
                    1. Be self-contained with minimal dependencies
                    2. Return exit code 0 if vulnerable, 1 if not vulnerable
                    3. Print detailed output about what was tested
                    4. Be safe and non-destructive
                    Output ONLY the Python code, no explanations."""
                },
                {
                    "role": "user", 
                    "content": f"Vulnerability: {vulnerability}\nTarget: {target_url}"
                }
            ],
            temperature=0.1,
            max_tokens=2000
        )
        
        script = response.choices[0].message.content
        
        # Clean up markdown code blocks if present
        script = script.replace('```python', '').replace('```', '').strip()
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'script': script,
                'model': model,
                'vulnerability': vulnerability,
                'target_url': target_url
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
