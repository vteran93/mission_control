from __future__ import annotations

import re
import time
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

import jwt
import requests

from config import GitHubSettings
from crew_runtime.providers import GitHubProvider
from delivery_tracking import DeliveryTrackingService
from operator_control import OperatorControlService


BLUEPRINT_BRANCH_PATTERN = re.compile(r"blueprint-(\d+)")


class GitHubOperatorService:
    def __init__(self, operator_control_service: OperatorControlService):
        self.operator_control_service = operator_control_service
        self.tracking_service = DeliveryTrackingService()
        self._installation_token_cache: dict[str, tuple[str, float]] = {}

    def build_dashboard(self) -> dict[str, Any]:
        settings = self.operator_control_service.build_effective_settings().github
        provider = GitHubProvider(settings)
        return {
            "auth_mode": self._auth_mode(settings),
            "configured": provider.healthcheck().configured,
            "provider_health": asdict(provider.healthcheck()),
            "repository": settings.repository,
            "default_base_branch": settings.default_base_branch,
            "protected_branches": list(settings.protected_branches),
            "required_approving_review_count": settings.required_approving_review_count,
            "dismiss_stale_reviews": settings.dismiss_stale_reviews,
            "require_conversation_resolution": settings.require_conversation_resolution,
        }

    def sync_protected_branches(
        self,
        *,
        dry_run: bool = False,
        branches: list[str] | None = None,
    ) -> dict[str, Any]:
        settings = self.operator_control_service.build_effective_settings().github
        repository = self._require_repository(settings)
        selected_branches = [branch.strip() for branch in (branches or settings.protected_branches) if branch.strip()]
        if not selected_branches:
            raise RuntimeError("No protected branches configured for GitHub sync.")

        auth_headers = self._build_auth_headers(settings)
        protection_payload = self._branch_protection_payload(settings)
        results: list[dict[str, Any]] = []
        for branch in selected_branches:
            if dry_run:
                status = "pending"
                summary = f"Dry-run branch protection prepared for {branch}."
                payload = {"branch": branch, "protection": protection_payload, "dry_run": True}
            else:
                response = requests.put(
                    f"{settings.api_url.rstrip('/')}/repos/{repository}/branches/{branch}/protection",
                    headers=auth_headers,
                    json=protection_payload,
                    timeout=15,
                )
                response.raise_for_status()
                payload = response.json()
                status = "synced"
                summary = f"Branch protection synced for {branch}."

            event = self.tracking_service.create_github_sync_event(
                repository=repository,
                event_type="branch_protection",
                action="sync",
                status=status,
                summary=summary,
                branch_name=branch,
                external_id=f"branch-protection:{repository}:{branch}",
                payload=payload,
            )
            results.append(event.to_dict())

        return {
            "repository": repository,
            "auth_mode": self._auth_mode(settings),
            "dry_run": dry_run,
            "branch_count": len(results),
            "events": results,
        }

    def sync_pull_requests(
        self,
        *,
        state: str = "all",
        per_page: int = 20,
    ) -> dict[str, Any]:
        settings = self.operator_control_service.build_effective_settings().github
        repository = self._require_repository(settings)
        auth_headers = self._build_auth_headers(settings)
        response = requests.get(
            f"{settings.api_url.rstrip('/')}/repos/{repository}/pulls",
            headers=auth_headers,
            params={"state": state, "per_page": max(1, min(per_page, 100))},
            timeout=15,
        )
        response.raise_for_status()
        pull_requests = response.json()
        events: list[dict[str, Any]] = []

        for item in pull_requests:
            head_ref = ((item.get("head") or {}).get("ref")) or ""
            base_ref = ((item.get("base") or {}).get("ref")) or ""
            blueprint_id = self._extract_blueprint_id(head_ref)
            payload = {
                "number": item.get("number"),
                "title": item.get("title"),
                "state": item.get("state"),
                "html_url": item.get("html_url"),
                "head_ref": head_ref,
                "base_ref": base_ref,
                "updated_at": item.get("updated_at"),
                "merged_at": item.get("merged_at"),
                "draft": item.get("draft"),
                "user": (item.get("user") or {}).get("login"),
            }
            event = self.tracking_service.create_github_sync_event(
                repository=repository,
                event_type="pull_request_snapshot",
                action="fetch",
                status="fetched",
                summary=f"Pull request #{item.get('number')} fetched from GitHub.",
                blueprint_id=blueprint_id,
                branch_name=head_ref or None,
                pull_request_number=item.get("number"),
                external_id=f"pull-request:{repository}:{item.get('number')}:{item.get('updated_at')}",
                payload=payload,
            )
            events.append(event.to_dict())

        return {
            "repository": repository,
            "auth_mode": self._auth_mode(settings),
            "pull_request_count": len(events),
            "events": events,
        }

    def list_recent_events(
        self,
        *,
        blueprint_id: int | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = self.tracking_service_query()
        if blueprint_id is not None:
            query = query.filter_by(project_blueprint_id=blueprint_id)
        rows = query.order_by(self.tracking_service_model.created_at.desc()).limit(max(1, min(limit, 200))).all()
        return [row.to_dict() for row in rows]

    @property
    def tracking_service_model(self):
        from database import GitHubSyncEventRecord

        return GitHubSyncEventRecord

    def tracking_service_query(self):
        return self.tracking_service_model.query

    @staticmethod
    def _extract_blueprint_id(head_ref: str) -> int | None:
        match = BLUEPRINT_BRANCH_PATTERN.search(head_ref or "")
        if match is None:
            return None
        return int(match.group(1))

    @staticmethod
    def _require_repository(settings: GitHubSettings) -> str:
        if not settings.repository:
            raise RuntimeError("GITHUB_REPOSITORY is not configured.")
        return settings.repository

    @staticmethod
    def _auth_mode(settings: GitHubSettings) -> str:
        if settings.app_id and settings.app_installation_id and settings.app_private_key:
            return "app"
        if settings.token:
            return "token"
        return "none"

    def _build_auth_headers(self, settings: GitHubSettings) -> dict[str, str]:
        token = self._resolve_access_token(settings)
        if not token:
            raise RuntimeError("GitHub credentials are not configured.")
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _resolve_access_token(self, settings: GitHubSettings) -> str | None:
        auth_mode = self._auth_mode(settings)
        if auth_mode == "token":
            return settings.token
        if auth_mode == "app":
            return self._resolve_installation_token(settings)
        return None

    def _resolve_installation_token(self, settings: GitHubSettings) -> str:
        assert settings.app_id is not None
        assert settings.app_installation_id is not None
        assert settings.app_private_key is not None

        cache_key = f"{settings.api_url}:{settings.app_installation_id}"
        cached = self._installation_token_cache.get(cache_key)
        if cached is not None and cached[1] > time.time() + 60:
            return cached[0]

        app_jwt = self._build_app_jwt(settings)
        response = requests.post(
            (
                f"{settings.api_url.rstrip('/')}/app/installations/"
                f"{settings.app_installation_id}/access_tokens"
            ),
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {app_jwt}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        expires_at = payload.get("expires_at")
        expiry_ts = time.time() + 300
        if expires_at:
            expiry_ts = datetime.fromisoformat(
                expires_at.replace("Z", "+00:00")
            ).astimezone(timezone.utc).timestamp()
        token = payload["token"]
        self._installation_token_cache[cache_key] = (token, expiry_ts)
        return token

    @staticmethod
    def _build_app_jwt(settings: GitHubSettings) -> str:
        assert settings.app_id is not None
        assert settings.app_private_key is not None
        now = int(time.time())
        private_key = settings.app_private_key.replace("\\n", "\n")
        return jwt.encode(
            {
                "iat": now - 60,
                "exp": now + 540,
                "iss": str(settings.app_id),
            },
            private_key,
            algorithm="RS256",
        )

    @staticmethod
    def _branch_protection_payload(settings: GitHubSettings) -> dict[str, Any]:
        return {
            "required_status_checks": None,
            "enforce_admins": True,
            "required_pull_request_reviews": {
                "dismiss_stale_reviews": settings.dismiss_stale_reviews,
                "require_code_owner_reviews": False,
                "required_approving_review_count": settings.required_approving_review_count,
            },
            "restrictions": None,
            "required_conversation_resolution": settings.require_conversation_resolution,
            "allow_force_pushes": False,
            "allow_deletions": False,
            "block_creations": False,
            "required_linear_history": False,
            "lock_branch": False,
            "allow_fork_syncing": True,
        }
