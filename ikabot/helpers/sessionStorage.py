#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import hashlib
import json
import logging
import os
import re
import sys
import time

from ikabot import config
from ikabot.helpers.aesCipher import AESCipher

logger = logging.getLogger(__name__)


def get_home_dir():
    """Returns the user's home directory across platforms."""
    home_env = "USERPROFILE" if config.isWindows else "HOME"
    return os.getenv(home_env) or os.path.expanduser("~")


def get_ikabot_dir():
    """Returns the path to ~/.ikabot directory."""
    return os.path.join(get_home_dir(), ".ikabot")


def get_global_config_path():
    """Returns the path to ~/.ikabot/global.json."""
    return os.path.join(get_ikabot_dir(), "global.json")


def get_users_dir():
    """Returns the path to ~/.ikabot/users directory."""
    return os.path.join(get_ikabot_dir(), "users")


def get_legacy_migration_path():
    """Returns the path to ~/.ikabot/.legacy_migration.enc."""
    return os.path.join(get_ikabot_dir(), ".legacy_migration.enc")


def sanitize_email(email):
    """
    Converts an email address into a safe, human-readable filename.
    e.g. 'player.one@gmail.com' -> 'player.one_gmail.com'
    """
    if not email:
        return "default_user"
    email_str = str(email).strip().lower()
    # Replace @ and forbidden characters with underscores
    sanitized = re.sub(r'[@\s/\\:*?"<>|]', '_', email_str)
    # Collapse multiple consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    return sanitized.strip("._") or "user"


def get_user_file_path(email):
    """Returns the path to the user's JSON file: ~/.ikabot/users/<sanitized_email>.json"""
    filename = f"{sanitize_email(email)}.json"
    return os.path.join(get_users_dir(), filename)


def get_saved_users():
    """Returns the list of saved user accounts (their emails) found in ~/.ikabot/users,
    excluding the default account used for empty mail."""
    users_dir = get_users_dir()
    if not os.path.isdir(users_dir):
        return []

    saved = []
    for filename in sorted(os.listdir(users_dir)):
        if not filename.endswith(".json"):
            continue
        if filename == f"{sanitize_email('')}.json":
            continue
        filepath = os.path.join(users_dir, filename)
        data = read_json_file(filepath, {})
        email = data.get("email") or filename[: -len(".json")]
        saved.append(email)
    return saved


def find_user_file_for_email(email):
    """
    Resolves an email to its session JSON file(s) in ~/.ikabot/users.

    Returns a tuple (matching_path, duplicados):
      - matching_path: path of the most recently modified matching file,
                       or None if no user file matches the email.
      - duplicados:    True if more than one file matches the email.
    The default_user file (empty mail) is never considered a match.
    """
    users_dir = get_users_dir()
    if not os.path.isdir(users_dir):
        return None, False

    candidates = []
    for filename in os.listdir(users_dir):
        if not filename.endswith(".json"):
            continue
        if filename == f"{sanitize_email('')}.json":
            continue
        filepath = os.path.join(users_dir, filename)
        data = read_json_file(filepath, {})
        stored_email = data.get("email") or filename[: -len(".json")]
        if stored_email and stored_email.lower() == email.strip().lower():
            candidates.append(filepath)

    if not candidates:
        return None, False

    # Pick the most recently modified file, considering mtime/size tuple
    matching_path = max(
        candidates,
        key=lambda p: (os.path.getmtime(p) if os.path.exists(p) else 0,
                       os.path.getsize(p) if os.path.exists(p) else 0),
    )
    return matching_path, len(candidates) > 1


def init_storage():
    """
    Initializes the storage layout:
    1. If ~/.ikabot is an existing regular file (legacy format), rename/move it
       to ~/.ikabot_legacy_backup.enc and then into ~/.ikabot/.legacy_migration.enc.
    2. Ensures ~/.ikabot/ and ~/.ikabot/users/ directories exist.
    3. Initializes ~/.ikabot/global.json with defaults if it does not exist.
    """
    home = get_home_dir()
    ika_path = os.path.join(home, ".ikabot")
    temp_legacy_backup = os.path.join(home, ".ikabot_legacy_backup.enc")

    # Step 1: Handle legacy single file if present
    if os.path.exists(ika_path) and os.path.isfile(ika_path):
        logger.info(f"Legacy .ikabot file detected at {ika_path}. Preparing migration...")
        try:
            os.replace(ika_path, temp_legacy_backup)
        except Exception as e:
            logger.error(f"Failed to rename legacy file: {e}")

    # Step 2: Ensure directories exist
    ika_dir = get_ikabot_dir()
    os.makedirs(ika_dir, exist_ok=True)
    os.makedirs(get_users_dir(), exist_ok=True)

    # Move temporary legacy backup into .ikabot/.legacy_migration.enc
    if os.path.exists(temp_legacy_backup):
        legacy_dest = get_legacy_migration_path()
        try:
            if not os.path.exists(legacy_dest):
                os.replace(temp_legacy_backup, legacy_dest)
            else:
                # Merge lines if destination already exists
                with open(temp_legacy_backup, "r", encoding="utf-8") as f_src:
                    src_content = f_src.read()
                with open(legacy_dest, "a", encoding="utf-8") as f_dst:
                    f_dst.write("\n" + src_content.strip())
                os.remove(temp_legacy_backup)
        except Exception as e:
            logger.error(f"Failed moving legacy backup into directory: {e}")

    # Step 3: Initialize global.json if missing
    global_path = get_global_config_path()
    if not os.path.exists(global_path):
        initial_global = {
            "logLevel": 2,
            "telegram": {},
            "discord": {},
            "custom_modules": {}
        }
        write_json_file(global_path, initial_global)


def read_json_file(filepath, default=None):
    """
    Reads JSON data freshly from disk.
    Allows hot-swapping by humans. If the file is temporarily being written
    or contains minor syntax errors, it retries briefly before falling back.
    """
    if default is None:
        default = {}

    if not os.path.exists(filepath):
        return default

    # Try up to 3 times in case another process / text editor is actively writing
    for attempt in range(3):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return default
                return json.loads(content)
        except (json.JSONDecodeError, OSError) as e:
            if attempt < 2:
                time.sleep(0.05)
                continue
            logger.warning(f"Error reading JSON from {filepath}: {e}")
            return default

    return default


def write_json_file(filepath, data):
    """
    Atomically writes data to disk as human-readable JSON (indent=2)
    using a temporary file and atomic replace to prevent corruptions.
    """
    dir_path = os.path.dirname(filepath)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    tmp_path = f"{filepath}.tmp.{os.getpid()}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, filepath)
    except Exception as e:
        logger.error(f"Failed to write JSON to {filepath}: {e}")
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        raise


def migrate_legacy_account(session_or_mail, password, custom_logger=None):
    """
    Checks if there is legacy data stored for this mail/password in ~/.ikabot/.legacy_migration.enc.
    If found, decrypts it, migrates data to global.json and users/<email>.json,
    and removes the migrated entry from the legacy file.
    """
    log = custom_logger or logger
    mail = session_or_mail.mail if hasattr(session_or_mail, "mail") else str(session_or_mail)
    legacy_file = get_legacy_migration_path()

    if not os.path.exists(legacy_file):
        return False

    entry_key = hashlib.sha256(
        "ikabot".encode("utf-8") + mail.encode("utf-8")
    ).hexdigest()

    try:
        with open(legacy_file, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except Exception as e:
        log.warning(f"Could not read legacy migration file: {e}")
        return False

    matching_line = None
    remaining_lines = []

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        if line_clean.startswith(entry_key):
            matching_line = line_clean
        else:
            remaining_lines.append(line_clean)

    if not matching_line:
        return False

    # Extract ciphertext (first 64 chars are entry_key)
    ciphertext = matching_line[64:].strip()
    cipher = AESCipher(mail, password)

    try:
        plaintext = cipher.decrypt(ciphertext)
        legacy_data = json.loads(plaintext, strict=False)
    except Exception as e:
        log.warning(f"Could not decrypt legacy session data for {mail}. Password might differ or data corrupted: {e}")
        return False

    log.info(f"Successfully decrypted legacy session data for {mail}. Migrating...")

    # 1. Migrate global shared items to global.json
    global_config = read_json_file(get_global_config_path(), {})
    user_file_path = get_user_file_path(mail)
    user_data = read_json_file(user_file_path, {})

    if "email" not in user_data:
        user_data["email"] = mail
    if "shared" not in user_data:
        user_data["shared"] = {}
    if "players" not in user_data:
        user_data["players"] = {}

    if "shared" in legacy_data and isinstance(legacy_data["shared"], dict):
        shared_dict = legacy_data["shared"]
        for key, val in shared_dict.items():
            if key == "lobby":
                # Lobby token belongs to user data
                user_data["shared"]["lobby"] = val
            else:
                # Global settings (telegram, discord, logLevel, custom_modules, etc.)
                if key not in global_config or not global_config[key]:
                    global_config[key] = val

    # 2. Migrate game accounts/players
    for key, val in legacy_data.items():
        if key == "shared":
            continue
        if isinstance(val, dict):
            user_data["players"][key] = val

    # 3. Write migrated data to disk
    write_json_file(get_global_config_path(), global_config)
    write_json_file(user_file_path, user_data)

    # 4. Remove migrated line from legacy file
    try:
        if remaining_lines:
            with open(legacy_file, "w", encoding="utf-8") as f:
                f.write("\n".join(remaining_lines) + "\n")
        else:
            # All lines migrated! Remove legacy file
            os.remove(legacy_file)
            log.info("All legacy session entries have been migrated. Legacy file removed.")
    except Exception as e:
        log.warning(f"Failed updating legacy migration file after migration: {e}")

    print(f"\n[Migration] Successfully migrated session data for '{mail}' to {user_file_path}\n")
    return True


def get_session_data(session, all_data=False):
    """
    ALWAYS reads fresh from disk to support hot-swapping.
    Merges global.json and users/<email>.json to return the exact session dictionary
    expected by Ikabot.
    """
    global_config = read_json_file(get_global_config_path(), {})
    mail = getattr(session, "mail", None) or ""
    user_file = get_user_file_path(mail)
    user_data = read_json_file(user_file, {})

    # Construct shared dict: global_config merged with user-specific shared (e.g. lobby)
    shared_data = dict(global_config)
    if "shared" in user_data and isinstance(user_data["shared"], dict):
        shared_data.update(user_data["shared"])

    if all_data:
        # Full data dictionary
        result = dict(user_data.get("players", {}))
        result["shared"] = shared_data
        return result

    # Return player/world/server specific session data
    username = getattr(session, "username", None)
    mundo = getattr(session, "mundo", None)
    servidor = getattr(session, "servidor", None)

    session_data = {}
    if username and mundo and servidor:
        # Look in "players" first, then root of user_data for human convenience
        players = user_data.get("players", user_data)
        try:
            session_data = dict(players[username][str(mundo)][servidor])
        except (KeyError, TypeError):
            session_data = {}

    session_data["shared"] = shared_data
    return session_data


def set_session_data(session, data, shared=False):
    """
    Writes session data to disk formatted as JSON (indent=2).
    Always reads latest disk state before writing to prevent overwriting
    concurrent updates or manual human edits.
    """
    mail = getattr(session, "mail", None) or ""
    global_path = get_global_config_path()
    user_path = get_user_file_path(mail)

    global_config = read_json_file(global_path, {})
    user_data = read_json_file(user_path, {})

    if "email" not in user_data:
        user_data["email"] = mail
    if "shared" not in user_data:
        user_data["shared"] = {}
    if "players" not in user_data:
        user_data["players"] = {}

    if shared:
        # Route shared items to global.json or user-level shared
        global_keys = {"logLevel", "telegram", "discord", "custom_modules"}
        global_modified = False

        for k, v in data.items():
            if k == "lobby":
                user_data["shared"]["lobby"] = v
            elif k in global_keys:
                global_config[k] = v
                global_modified = True
            else:
                # Default: save to both user shared and global config
                user_data["shared"][k] = v
                global_config[k] = v
                global_modified = True

        if global_modified:
            write_json_file(global_path, global_config)
        write_json_file(user_path, user_data)
    else:
        # Update specific account under players[username][mundo][servidor]
        username = getattr(session, "username", None)
        mundo = str(getattr(session, "mundo", ""))
        servidor = getattr(session, "servidor", None)

        if username and mundo and servidor:
            if username not in user_data["players"]:
                user_data["players"][username] = {}
            if mundo not in user_data["players"][username]:
                user_data["players"][username][mundo] = {}
            user_data["players"][username][mundo][servidor] = data

        write_json_file(user_path, user_data)


def delete_session_data(session):
    """Deletes the user's session JSON file."""
    mail = getattr(session, "mail", None) or ""
    user_path = get_user_file_path(mail)
    if os.path.exists(user_path):
        try:
            os.remove(user_path)
            logger.info(f"Deleted user session file at {user_path}")
        except Exception as e:
            logger.error(f"Failed deleting user session file at {user_path}: {e}")
