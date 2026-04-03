from __future__ import annotations

import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any


def _get_table_info(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.Error:
        return []

    result: list[dict[str, Any]] = []
    for cid, name, col_type, notnull, default_value, pk in rows:
        result.append(
            {
                "cid": cid,
                "name": name,
                "type": (col_type or "").upper(),
                "notnull": bool(notnull),
                "default": default_value,
                "pk": bool(pk),
            }
        )
    return result


def _build_timestamp(column_type: str) -> int | str:
    if "INT" in column_type or "REAL" in column_type or "NUM" in column_type:
        return int(time.time())
    return datetime.now(timezone.utc).isoformat()


def _normalize_author(author: str | None) -> str:
    value = (author or "@System").strip()
    return value or "@System"


def _normalize_system_post_content(post: dict[str, Any]) -> str:
    content = str(post.get("content") or "").strip()
    author = _normalize_author(post.get("author"))
    metadata = post.get("metadata") if isinstance(post.get("metadata"), dict) else {}
    source = metadata.get("source")
    if not content:
        content = "시스템 공지가 게시되었습니다."
    if source:
        return f"[{source}] {content}"
    if author and author not in content:
        return f"{author}: {content}"
    return content


def _first_existing(columns: set[str], *candidates: str) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _lookup_system_user(conn: sqlite3.Connection, author: str, user_columns: list[dict[str, Any]]) -> int | None:
    columns = {col["name"] for col in user_columns}
    lookup_column = _first_existing(columns, "user_name", "username", "name")
    if not lookup_column:
        return None
    row = conn.execute(
        f"SELECT user_id FROM user WHERE {lookup_column} = ? ORDER BY user_id ASC LIMIT 1",
        (author,),
    ).fetchone()
    if row:
        return int(row[0])
    return None


def _create_system_user(conn: sqlite3.Connection, author: str, user_columns: list[dict[str, Any]]) -> int | None:
    columns = {col["name"] for col in user_columns}
    now_value = {
        col["name"]: _build_timestamp(col["type"]) for col in user_columns if col["name"] in {"created_at", "updated_at"}
    }
    author_name = author.lstrip("@") or "System"
    payload = {
        "name": author_name,
        "user_name": author,
        "username": author,
        "screen_name": author,
        "display_name": author_name,
        "profile_name": author_name,
        "bio": "System-generated injected context",
        "info": json.dumps({"system_user": True, "author": author}, ensure_ascii=False),
        "metadata": json.dumps({"system_user": True, "author": author}, ensure_ascii=False),
        "created_at": now_value.get("created_at"),
        "updated_at": now_value.get("updated_at"),
    }

    fields: dict[str, Any] = {}
    for column in user_columns:
        name = column["name"]
        if column["pk"] and name == "user_id":
            continue
        if name in payload and payload[name] is not None:
            fields[name] = payload[name]
        elif column["notnull"] and column["default"] is None and name not in fields:
            if "INT" in column["type"] or "REAL" in column["type"] or "NUM" in column["type"]:
                fields[name] = 0
            else:
                fields[name] = ""

    if not fields:
        return None

    field_names = list(fields.keys())
    placeholders = ", ".join("?" for _ in field_names)
    conn.execute(
        f"INSERT INTO user ({', '.join(field_names)}) VALUES ({placeholders})",
        [fields[name] for name in field_names],
    )
    row = conn.execute(
        "SELECT user_id FROM user ORDER BY user_id DESC LIMIT 1"
    ).fetchone()
    if row:
        return int(row[0])
    return None


def _ensure_system_user(conn: sqlite3.Connection, author: str) -> int | None:
    user_columns = _get_table_info(conn, "user")
    if not user_columns:
        return None
    existing_user_id = _lookup_system_user(conn, author, user_columns)
    if existing_user_id is not None:
        return existing_user_id
    return _create_system_user(conn, author, user_columns)


def _build_post_fields(post_columns: list[dict[str, Any]], user_id: int, content: str, metadata: dict[str, Any], author: str) -> dict[str, Any]:
    columns = {col["name"] for col in post_columns}
    now_values = {
        col["name"]: _build_timestamp(col["type"]) for col in post_columns if col["name"] in {"created_at", "updated_at"}
    }
    payload = {
        "user_id": user_id,
        "content": content,
        "text": content,
        "body": content,
        "title": content[:80],
        "author": author,
        "user_name": author,
        "info": json.dumps(metadata, ensure_ascii=False),
        "metadata": json.dumps(metadata, ensure_ascii=False),
        "status": "published",
        "visibility": "public",
        "subreddit": metadata.get("subreddit", "worldnews"),
        "created_at": now_values.get("created_at"),
        "updated_at": now_values.get("updated_at"),
    }

    fields: dict[str, Any] = {}
    for column in post_columns:
        name = column["name"]
        if column["pk"] and name == "post_id":
            continue
        if name in payload and payload[name] is not None:
            fields[name] = payload[name]
        elif column["notnull"] and column["default"] is None and name not in fields:
            if name == "user_id":
                fields[name] = user_id
            elif name in {"created_at", "updated_at"}:
                fields[name] = _build_timestamp(column["type"])
            elif any(token in name for token in ("content", "text", "body")):
                fields[name] = content
            elif name == "title":
                fields[name] = content[:80]
            elif any(token in name for token in ("author", "user_name", "username", "name")):
                fields[name] = author
            elif name in {"info", "metadata"}:
                fields[name] = json.dumps(metadata, ensure_ascii=False)
            elif "INT" in column["type"] or "REAL" in column["type"] or "NUM" in column["type"]:
                fields[name] = 0
            else:
                fields[name] = ""

    return fields


def inject_context_into_db(
    db_path: str,
    platform: str,
    context: dict[str, Any],
    logger: Any | None = None,
) -> int:
    if not context or not db_path:
        return 0

    posts = context.get("system_posts", []) if isinstance(context, dict) else []
    if not isinstance(posts, list) or not posts:
        return 0

    injected = 0
    conn = sqlite3.connect(db_path)
    try:
        post_columns = _get_table_info(conn, "post")
        if not post_columns:
            return 0

        for post in posts:
            if not isinstance(post, dict):
                continue
            target_platform = (post.get("platform") or "twitter").strip().lower()
            if target_platform and target_platform != platform:
                continue

            author = _normalize_author(post.get("author"))
            metadata = post.get("metadata") if isinstance(post.get("metadata"), dict) else {}
            user_id = _ensure_system_user(conn, author)
            if user_id is None:
                continue

            content = _normalize_system_post_content(post)
            fields = _build_post_fields(post_columns, user_id, content, metadata, author)
            if not fields:
                continue

            field_names = list(fields.keys())
            placeholders = ", ".join("?" for _ in field_names)
            conn.execute(
                f"INSERT INTO post ({', '.join(field_names)}) VALUES ({placeholders})",
                [fields[name] for name in field_names],
            )
            injected += 1

        conn.commit()
        return injected
    except sqlite3.Error as exc:
        if logger:
            logger.warning("[round_control] Failed to inject context into %s DB: %s", platform, exc)
        return injected
    finally:
        conn.close()


def merge_env_constraints(
    existing_constraints: list[dict[str, Any]],
    env_constraints: list[dict[str, Any]],
    agent_names: dict[int, str],
    logger: Any | None = None,
) -> list[dict[str, Any]]:
    merged = list(existing_constraints)
    for raw_constraint in env_constraints:
        if not isinstance(raw_constraint, dict):
            continue
        if raw_constraint.get("type") != "block_action":
            if logger:
                logger.info("[round_control] Unsupported constraint type skipped: %s", raw_constraint.get("type"))
            continue

        target_ids = resolve_target_agent_ids(raw_constraint.get("target_agents", []), agent_names)
        if not target_ids:
            continue

        remaining_rounds = raw_constraint.get("duration_rounds", 1)
        try:
            remaining_rounds = max(1, int(remaining_rounds))
        except (TypeError, ValueError):
            remaining_rounds = 1

        blocked_actions = raw_constraint.get("blocked_actions", [])
        if not isinstance(blocked_actions, list):
            blocked_actions = []

        merged.append(
            {
                "type": "block_action",
                "target_agent_ids": sorted(target_ids),
                "blocked_actions": [str(action).lower() for action in blocked_actions],
                "remaining_rounds": remaining_rounds,
                "reason": raw_constraint.get("reason", ""),
            }
        )
    return merged


def resolve_target_agent_ids(target_agents: list[Any], agent_names: dict[int, str]) -> set[int]:
    if not isinstance(target_agents, list):
        return set()

    lowered_name_map = {name.lower(): agent_id for agent_id, name in agent_names.items()}
    resolved: set[int] = set()
    for target in target_agents:
        if isinstance(target, int):
            resolved.add(target)
            continue
        value = str(target).strip()
        if not value:
            continue
        if value.isdigit():
            resolved.add(int(value))
            continue
        lowered = value.lower()
        if lowered in lowered_name_map:
            resolved.add(lowered_name_map[lowered])
            continue
        if lowered.startswith("agent_"):
            suffix = lowered.split("agent_", 1)[1]
            if suffix.isdigit():
                resolved.add(int(suffix))
                continue
    return resolved


def is_agent_blocked(
    constraints: list[dict[str, Any]],
    agent_id: int,
    action_name: str | None = None,
) -> bool:
    normalized_action = str(action_name or "").strip().lower()
    for constraint in constraints:
        if agent_id not in constraint.get("target_agent_ids", []):
            continue
        if constraint.get("remaining_rounds", 0) <= 0:
            continue
        blocked_actions = [str(v).strip().lower() for v in constraint.get("blocked_actions", [])]
        if not blocked_actions:
            return True
        if normalized_action and normalized_action in blocked_actions:
            return True
    return False


def tick_constraints(constraints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    for constraint in constraints:
        remaining = int(constraint.get("remaining_rounds", 0)) - 1
        if remaining > 0:
            next_constraint = dict(constraint)
            next_constraint["remaining_rounds"] = remaining
            updated.append(next_constraint)
    return updated
