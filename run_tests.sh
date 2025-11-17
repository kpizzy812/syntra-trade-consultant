#!/bin/bash
cd "/Users/a1/Projects/Syntra Trade Consultant"
source .venv/bin/activate
pytest tests/ -v --cov=src --cov-report=term-missing
