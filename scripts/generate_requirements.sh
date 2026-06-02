#!/bin/bash

echo "Generating requirements.txt from pyproject.toml..."

uv pip compile pyproject.toml -o requirements.txt