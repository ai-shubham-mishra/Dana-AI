"""Clones the MMM library at an exact branch, sparse-checked-out to the library folder only."""

from __future__ import annotations

import base64
import subprocess
from pathlib import Path
from typing import Callable

from integrations.provisioning.models import SourceCheckout

Runner = Callable[..., subprocess.CompletedProcess]


class GitSourceError(RuntimeError):
    pass


class GitSourceCloner:
    def __init__(
        self,
        repo_url: str,
        branch: str,
        library_subdir: str,
        dest: Path,
        token: str | None = None,
        runner: Runner = subprocess.run,
    ) -> None:
        self.repo_url = repo_url
        self.branch = branch
        self.library_subdir = library_subdir
        self.dest = dest
        self._token = token
        self._runner = runner

    def checkout(self) -> SourceCheckout:
        if (self.dest / ".git").is_dir():
            self._git("fetch", "--depth", "1", "origin", self.branch, cwd=self.dest)
            self._git("reset", "--hard", "FETCH_HEAD", cwd=self.dest)
        else:
            self.dest.parent.mkdir(parents=True, exist_ok=True)
            self._git(
                "clone", "--depth", "1", "--filter=blob:none", "--sparse",
                "--branch", self.branch, self.repo_url, str(self.dest),
            )
        self._git("sparse-checkout", "set", self.library_subdir, cwd=self.dest)
        sha = self._git("rev-parse", "HEAD", cwd=self.dest).strip()
        library_dir = self.dest / self.library_subdir
        if not (library_dir / "Dockerfile.api").is_file():
            raise GitSourceError(f"Dockerfile.api not found under {library_dir} at {sha}")
        return SourceCheckout(repo_url=self.repo_url, branch=self.branch, sha=sha, library_dir=library_dir)

    def _auth_args(self) -> list[str]:
        if not self._token:
            return []
        basic = base64.b64encode(f"x-access-token:{self._token}".encode()).decode()
        return ["-c", f"http.extraheader=AUTHORIZATION: basic {basic}"]

    def _redact(self, text: str) -> str:
        if not self._token:
            return text
        basic = base64.b64encode(f"x-access-token:{self._token}".encode()).decode()
        return text.replace(self._token, "***").replace(basic, "***")

    def _git(self, *args: str, cwd: Path | None = None) -> str:
        argv = ["git", *self._auth_args(), *args]
        result = self._runner(argv, cwd=cwd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            detail = self._redact((result.stderr or "").strip())
            raise GitSourceError(f"git {args[0]} failed: {detail}")
        return result.stdout
