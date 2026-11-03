import re
import secrets
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from pymongo import DESCENDING

from integrations.plans.markdown import InvalidPlan, parse_plan_markdown, render_plan_markdown
from integrations.training.mmm.plan import MMMPlan, PlanError

PLAN_PROJECTION = {"_id": 0, "org_id": 0}
PLAN_NAME_MAX = 80
PLAN_NAME_RE = re.compile(r"^\w[\w \-.()·]*$")
VISIBILITIES = ("private", "org")
ID_BYTES = 8
SLUG_MAX = 40
SLUG_COMMANDS = ("plan", "plans")


class PlanNameTaken(Exception):
    def __init__(self, name: str):
        super().__init__(f"a plan named '{name}' already exists")
        self.name = name


def normalize_plan_name(raw: str | None) -> str:
    name = " ".join((raw or "").split())
    if not name or len(name) > PLAN_NAME_MAX or not PLAN_NAME_RE.match(name):
        raise InvalidPlan(
            f"plan name must be 1-{PLAN_NAME_MAX} characters: letters, digits, spaces and - _ . ( ) ·"
        )
    return name


def validate_visibility(raw: str) -> str:
    if raw not in VISIBILITIES:
        raise InvalidPlan(f"visibility must be one of {', '.join(VISIBILITIES)}")
    return raw


def validate_spec(raw: dict[str, Any]) -> dict[str, Any]:
    """Check a training recipe with the same rules a run uses and return it JSON-ready. Rationale is not part of a plan."""
    fields = {key: value for key, value in (raw or {}).items() if key != "rationale"}
    try:
        plan = MMMPlan(**fields)
    except (ValidationError, PlanError) as exc:
        raise InvalidPlan(f"the plan is invalid: {exc}") from exc
    return plan.model_dump(mode="json", exclude={"rationale"})


def content_to_spec(content: str) -> tuple[str, dict[str, Any]]:
    """Parse the bulleted markdown, validate it, and return the canonical markdown with the derived spec."""
    spec = validate_spec(parse_plan_markdown(content))
    return render_plan_markdown(spec), spec


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:SLUG_MAX].strip("-")
    return slug or "plan"


def plan_slug(doc: dict[str, Any]) -> str:
    return doc.get("slug") or slugify(doc.get("name") or "")


def _unique_slug(name: str, taken: set[str]) -> str:
    base = slugify(name)
    slug = base
    while slug in taken or slug in SLUG_COMMANDS:
        slug = f"{base}-{secrets.token_hex(2)}"
    return slug


def _now() -> datetime:
    return datetime.now(UTC)


class PlanStore:
    """Saved training recipes. A user sees their own plans plus plans shared with the org."""

    def __init__(self, db: Any):
        self._db = db

    def _visible(self, org_id: str, user_id: str) -> dict[str, Any]:
        return {"org_id": org_id, "$or": [{"owner_id": user_id}, {"visibility": "org"}]}

    async def list_visible(self, *, org_id: str, user_id: str) -> list[dict[str, Any]]:
        cursor = self._db.plans.find(self._visible(org_id, user_id), PLAN_PROJECTION).sort("updated_at", DESCENDING)
        return [doc async for doc in cursor]

    async def get_visible(self, *, org_id: str, user_id: str, plan_id: str) -> dict[str, Any] | None:
        return await self._db.plans.find_one({**self._visible(org_id, user_id), "id": plan_id}, PLAN_PROJECTION)

    async def find_by_slug(self, *, org_id: str, user_id: str, slug: str) -> dict[str, Any] | None:
        """Resolve /<slug>. A user's own plan wins over a shared plan with the same slug."""
        matches = [doc for doc in await self.list_visible(org_id=org_id, user_id=user_id) if plan_slug(doc) == slug]
        owned = [doc for doc in matches if doc.get("owner_id") == user_id]
        picked = owned or matches
        return _public(picked[0]) if picked else None

    async def ensure_name_free(self, *, org_id: str, user_id: str, name: str, exclude_id: str | None = None) -> None:
        query: dict[str, Any] = {
            **self._visible(org_id, user_id),
            "name": {"$regex": f"^{re.escape(name)}$", "$options": "i"},
        }
        if exclude_id:
            query["id"] = {"$ne": exclude_id}
        if await self._db.plans.find_one(query, {"_id": 1}) is not None:
            raise PlanNameTaken(name)

    async def create(
        self,
        *,
        org_id: str,
        user_id: str,
        owner_email: str | None,
        name: str,
        description: str,
        visibility: str,
        content: str,
    ) -> dict[str, Any]:
        name = normalize_plan_name(name)
        visibility = validate_visibility(visibility)
        content, spec = content_to_spec(content)
        await self.ensure_name_free(org_id=org_id, user_id=user_id, name=name)
        taken = {
            plan_slug(doc)
            async for doc in self._db.plans.find({"org_id": org_id}, {"_id": 0, "name": 1, "slug": 1})
        }
        now = _now()
        doc = {
            "id": secrets.token_hex(ID_BYTES),
            "org_id": org_id,
            "owner_id": user_id,
            "owner_email": owner_email,
            "name": name,
            "slug": _unique_slug(name, taken),
            "description": description.strip(),
            "visibility": visibility,
            "content": content,
            "spec": spec,
            "created_at": now,
            "updated_at": now,
        }
        await self._db.plans.insert_one(dict(doc))
        return _public(doc)

    async def update(
        self, *, org_id: str, user_id: str, plan_id: str, changes: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Owner-only edit. Returns None when the plan is missing or not owned by this user."""
        current = await self._db.plans.find_one({"org_id": org_id, "owner_id": user_id, "id": plan_id}, {"_id": 0})
        if current is None:
            return None
        updates: dict[str, Any] = {}
        if "name" in changes:
            updates["name"] = normalize_plan_name(changes["name"])
        if "description" in changes:
            updates["description"] = (changes["description"] or "").strip()
        if "visibility" in changes:
            updates["visibility"] = validate_visibility(changes["visibility"])
        if "content" in changes:
            updates["content"], updates["spec"] = content_to_spec(changes["content"])
        if "name" in updates or "visibility" in updates:
            await self.ensure_name_free(
                org_id=org_id,
                user_id=user_id,
                name=updates.get("name", current["name"]),
                exclude_id=plan_id,
            )
        updates["updated_at"] = _now()
        await self._db.plans.update_one({"org_id": org_id, "owner_id": user_id, "id": plan_id}, {"$set": updates})
        return _public({**current, **updates})

    async def delete(self, *, org_id: str, user_id: str, plan_id: str) -> bool:
        result = await self._db.plans.delete_one({"org_id": org_id, "owner_id": user_id, "id": plan_id})
        return result.deleted_count == 1


def _public(doc: dict[str, Any]) -> dict[str, Any]:
    public = {key: value for key, value in doc.items() if key not in ("_id", "org_id")}
    if "content" not in public and "spec" in public:
        public["content"] = render_plan_markdown(public["spec"])
    public["slug"] = plan_slug(public)
    return public
