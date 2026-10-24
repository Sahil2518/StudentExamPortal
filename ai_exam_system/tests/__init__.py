"""
Backend test suite for the AI Adaptive Exam System.

Run all tests with:
    cd ai_exam_system
    D:\\python\\python.exe -m pytest tests/ -v

Individual test groups:
    D:\\python\\python.exe -m pytest tests/test_auth.py -v
    D:\\python\\python.exe -m pytest tests/test_exam_lifecycle.py -v
    D:\\python\\python.exe -m pytest tests/test_proctoring.py -v

These tests use a real database connection from .env.
They create test users with unique emails to avoid collisions with real data.
They clean up after themselves by deleting the created test records.
"""
