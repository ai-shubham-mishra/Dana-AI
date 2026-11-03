"""Command line entry point: python -m integrations.provisioning <run_id> [--no-cloud]."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from integrations.provisioning.config import ProvisioningConfig
from integrations.provisioning.orchestrator import build_default_orchestrator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m integrations.provisioning")
    parser.add_argument("run_id", help="Training run id under var/training/<run_id>/")
    parser.add_argument("--no-cloud", action="store_true", help="Skip the (mocked) Azure Container Apps step")
    args = parser.parse_args(argv)

    orchestrator = build_default_orchestrator(ProvisioningConfig.from_env())
    result = orchestrator.provision(args.run_id, deploy_cloud=not args.no_cloud)
    print(json.dumps(asdict(result), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
