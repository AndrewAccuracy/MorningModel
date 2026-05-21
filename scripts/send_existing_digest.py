import argparse
import os
import re
from pathlib import Path

from better_morning.config import get_secret, load_global_config
from better_morning.document_generator import DocumentGenerator


DEFAULT_ENV_FILE = ".env.local"
DEFAULT_DIGEST_PATTERN = "daily-digest-*.md"


def load_env_file(env_path: Path) -> None:
    """Load simple KEY=VALUE pairs from .env.local without overriding existing vars."""
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if value and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]

        os.environ.setdefault(key, value)


def find_latest_digest(root: Path) -> Path:
    candidates = sorted(root.glob(DEFAULT_DIGEST_PATTERN))
    if not candidates:
        raise FileNotFoundError(
            f"No digest files matched '{DEFAULT_DIGEST_PATTERN}' in {root}"
        )
    return candidates[-1]


def infer_subject(digest_path: Path) -> str:
    match = re.search(r"(\d{4}-\d{2}-\d{2})", digest_path.name)
    suffix = match.group(1) if match else digest_path.stem
    return f"[Morning Brief] AI + Finance Daily Digest | {suffix}"


def infer_smtp_settings(username: str) -> tuple[str | None, int | None]:
    if "@" not in username:
        return None, None

    domain = username.split("@", 1)[1].lower()
    if domain == "qq.com":
        return "smtp.qq.com", 465
    if domain == "icloud.com":
        return "smtp.mail.me.com", 587
    return None, None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send an existing daily digest Markdown file via the configured SMTP account."
    )
    parser.add_argument(
        "--digest",
        help="Path to an existing Markdown digest. Defaults to the latest daily-digest-*.md file.",
    )
    parser.add_argument(
        "--subject",
        help="Override the email subject. Defaults to the standard Morning Brief subject with the digest date.",
    )
    parser.add_argument(
        "--env-file",
        default=DEFAULT_ENV_FILE,
        help="Environment file to load before sending. Defaults to .env.local.",
    )
    parser.add_argument(
        "--smtp-server",
        help="Override SMTP server for this send.",
    )
    parser.add_argument(
        "--smtp-port",
        type=int,
        help="Override SMTP port for this send.",
    )
    args = parser.parse_args()

    root = Path.cwd()
    load_env_file(root / args.env_file)

    digest_path = Path(args.digest) if args.digest else find_latest_digest(root)
    if not digest_path.is_absolute():
        digest_path = root / digest_path

    body = digest_path.read_text(encoding="utf-8")
    config = load_global_config()
    smtp_username = get_secret(
        config.output_settings.smtp_username_env, "SMTP Username"
    )
    inferred_server, inferred_port = infer_smtp_settings(smtp_username)
    config.output_settings.smtp_server = (
        args.smtp_server or os.getenv("BETTER_MORNING_SMTP_SERVER") or inferred_server
    )
    config.output_settings.smtp_port = (
        args.smtp_port
        or int(os.getenv("BETTER_MORNING_SMTP_PORT", "0") or 0)
        or inferred_port
        or config.output_settings.smtp_port
    )
    recipient_email = get_secret(
        config.output_settings.recipient_email_env, "Recipient Email"
    )
    subject = args.subject or infer_subject(digest_path)

    document_generator = DocumentGenerator(config.output_settings, config)
    print(f"Sending digest from {digest_path.name}...")
    document_generator.send_via_email(subject, body, recipient_email)


if __name__ == "__main__":
    main()
