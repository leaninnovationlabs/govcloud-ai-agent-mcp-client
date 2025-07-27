#!/usr/bin/env python3
"""
AWS Setup Validation Script for GovCloud AI Agent

This script validates that your AWS credential chain is properly configured
for the application to access AWS Bedrock services.

Usage:
    python validate_aws_setup.py
"""

import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent / "app"))

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    from app.core.config import get_settings
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("💡 Try running: uv sync")
    sys.exit(1)


def main():
    """Validate AWS setup for the application."""
    print("🔍 Validating AWS Setup for GovCloud AI Agent")
    print("=" * 50)
    
    # Load application settings
    try:
        settings = get_settings()
        print(f"✅ Configuration loaded")
        print(f"   📍 Region: {settings.aws_region}")
        print(f"   🤖 Model: {settings.claude_model_id}")
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        return False
    
    # Test AWS credential chain
    print(f"\n🔐 Testing AWS Credential Chain...")
    try:
        sts = boto3.client('sts', region_name=settings.aws_region)
        identity = sts.get_caller_identity()
        print(f"✅ AWS credentials found")
        print(f"   👤 User/Role: {identity.get('Arn', 'Unknown')}")
        print(f"   🏢 Account: {identity.get('Account', 'Unknown')}")
    except NoCredentialsError:
        print("❌ No AWS credentials found!")
        print("💡 Setup guide:")
        print("   For local development: aws configure")
        print("   For AWS SSO: aws configure sso")
        print("   For production: use IAM roles")
        return False
    except ClientError as e:
        print(f"❌ AWS credential error: {e}")
        return False
    
    # Test Bedrock access
    print(f"\n🧠 Testing AWS Bedrock Access...")
    try:
        bedrock = boto3.client('bedrock', region_name=settings.aws_region)
        
        # Test listing foundation models
        response = bedrock.list_foundation_models()
        model_count = len(response.get('modelSummaries', []))
        print(f"✅ Bedrock API accessible")
        print(f"   📊 Available models: {model_count}")
        
        # Check if Claude 3.5 Sonnet is available
        claude_models = [
            model for model in response.get('modelSummaries', [])
            if 'claude-3-5-sonnet' in model.get('modelId', '').lower()
        ]
        
        if claude_models:
            print(f"✅ Claude 3.5 Sonnet models found: {len(claude_models)}")
            for model in claude_models:
                print(f"   🎯 {model['modelId']}")
        else:
            print("⚠️  Claude 3.5 Sonnet models not found")
            print("💡 You may need to request model access in the AWS Bedrock console")
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == 'AccessDeniedException':
            print("❌ Access denied to Bedrock")
            print("💡 Your AWS user/role needs 'bedrock:*' permissions")
        elif error_code == 'UnauthorizedOperation':
            print("❌ Unauthorized operation")
            print("💡 Check IAM permissions and Bedrock service availability")
        else:
            print(f"❌ Bedrock error ({error_code}): {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    
    # Test specific model access
    print(f"\n🎯 Testing Specific Model Access...")
    try:
        bedrock = boto3.client('bedrock', region_name=settings.aws_region)
        response = bedrock.get_foundation_model(modelIdentifier=settings.claude_model_id)
        print(f"✅ Target model accessible: {settings.claude_model_id}")
        print(f"   📝 Model name: {response['modelDetails']['modelName']}")
        print(f"   🏷️  Provider: {response['modelDetails']['providerName']}")
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == 'AccessDeniedException':
            print(f"❌ Access denied to model: {settings.claude_model_id}")
            print("💡 Request access to this model in AWS Bedrock console")
        else:
            print(f"❌ Model access error ({error_code}): {e}")
        return False
    
    print(f"\n🎉 AWS Setup Validation Complete!")
    print("🚀 Your application is ready to use AWS Bedrock")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 