"""Provisions an MMM API container from a trained Dana model.

Flow: resolve var/training/<run_id>/mmm_model.nc -> clone the MMM library (staging, mmm-library/) ->
build a per-run Docker context with the model and a local-model guard -> docker build and run ->
wait for /health -> deploy the Azure Container App through ARM (WireMock in local runs).

Run from backend/: python -m integrations.provisioning <run_id> [--no-cloud]
"""
