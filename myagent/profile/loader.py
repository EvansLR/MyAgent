"""Load persistent agent profile instruction files."""

from pathlib import Path


DEFAULT_PROFILE_SUBPATH = Path(".myagent") / "profile"

PROFILE_FILES = {
    "agent": "AGENT.md",
    "user": "USER.md",
    "tools": "TOOLS.md",
}


class ProfileLoader:
    """Read personal assistant profile files and expose them to ContextBuilder."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else Path.home() / DEFAULT_PROFILE_SUBPATH

    def load_file(self, filename: str) -> str:
        """Return a profile file, or an empty string if it is missing."""
        path = self.root / filename
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""

    def exists(self, filename: str) -> bool:
        """Check whether a profile file exists."""
        return (self.root / filename).exists()

    def present_files(self) -> list[str]:
        """Return the profile files that currently exist."""
        return [
            filename
            for filename in PROFILE_FILES.values()
            if self.exists(filename)
        ]

    def missing_files(self) -> list[str]:
        """Return the profile files that do not exist."""
        return [
            filename
            for filename in PROFILE_FILES.values()
            if not self.exists(filename)
        ]

    def to_summary_data(self) -> dict[str, object]:
        """Return a compact summary of profile file state."""
        return {
            "profile_root": str(self.root),
            "files_present": self.present_files(),
            "files_missing": self.missing_files(),
        }
