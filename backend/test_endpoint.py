#!/usr/bin/env python3
"""
Simple test script to verify the message retrieval endpoint works without OpenAI API key.
"""

import asyncio
import sys
import os

# Add the backend app to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from fastapi.testclient import TestClient
from app.app import app

def test_message_endpoint():
    """Test that getting messages doesn't require OpenAI API key."""
    client = TestClient(app)
    
    # Test 1: Get messages for non-existent conversation (should return 404)
    print("Testing non-existent conversation...")
    response = client.get("/conversations/999/messages")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    # Test 2: Create a conversation first
    print("\nCreating a new conversation...")
    create_response = client.post("/conversations/new")
    print(f"Status: {create_response.status_code}")
    print(f"Response: {create_response.json()}")
    assert create_response.status_code == 201
    
    conversation_data = create_response.json()["data"]
    conversation_id = conversation_data["id"]
    
    # Test 3: Get messages for empty conversation (should return empty array)
    print(f"\nGetting messages for conversation {conversation_id}...")
    response = client.get(f"/conversations/{conversation_id}/messages")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["data"] == [], f"Expected empty array, got {response_data['data']}"
    
    print("\n✅ All tests passed! The endpoint works correctly without OpenAI API key.")

if __name__ == "__main__":
    test_message_endpoint() 