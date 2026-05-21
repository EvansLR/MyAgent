"""Small risk classifier for shell commands."""

from __future__ import annotations

from enum import Enum
import re


class ShellRisk(str, Enum):
    """Execution policy for one shell command."""

    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"


_CONFIRM_OPERATORS = (";", "&&", "||", ">", "<", "`", "$(", "${")

_CONFIRM_PREFIXES = frozenset({
    "rm", "del", "format", "mkfs", "dd", "chmod", "chown",
    "sudo", "su",
    "remove-item", "erase", "rmdir", "rd",
    "set-content", "add-content", "out-file", "new-item",
    "move-item", "copy-item", "rename-item", "clear-content",
    "invoke-expression", "iex", "start-process",
})

_READONLY_PREFIXES = frozenset({
    "echo", "cat", "ls", "dir", "pwd", "whoami", "hostname",
    "date", "uname", "df", "du", "ps", "top", "env", "which", "where",
    "find", "grep", "head", "tail", "wc", "type",
    "wmic", "powercfg", "systeminfo", "ver", "winver",
    "get-process", "gps", "measure-object", "select-object",
    "sort-object", "where-object", "format-table", "format-list", "out-string",
    "get-ciminstance", "get-wmiobject", "get-computerinfo",
    "get-childitem", "gci", "get-content", "gc", "select-string", "sls",
    "get-command", "get-location", "gl", "test-path", "resolve-path",
    "pmset", "system_profiler", "sw_vers", "sysctl",
    "acpi", "upower", "lshw", "lspci", "lsusb", "dmidecode",
})

_VERSION_COMMANDS = frozenset({
    "python", "python3", "py", "node", "go", "rustc", "cargo",
    "java", "javac", "dotnet", "gcc", "g++", "clang",
    "pip", "pip3", "npm", "cmake",
})

_VERSION_FLAGS = frozenset({"--version", "-version", "-v", "/version"})

_PYTHON_READONLY_MODULES = frozenset({"pytest", "compileall"})

_GIT_READONLY_SUBCOMMANDS = frozenset({
    "status", "log", "show", "diff", "branch", "remote", "rev-parse",
    "ls-files", "grep", "blame", "describe", "tag",
})


def classify_shell_command(command: str) -> ShellRisk:
    """Classify a shell command as allow, confirm, or deny."""
    lowered = command.lower().strip()
    if not lowered:
        return ShellRisk.CONFIRM

    if "|" in lowered:
        return _classify_pipeline(lowered)
    return _classify_segment(lowered)


def _classify_pipeline(command: str) -> ShellRisk:
    segments = [segment.strip() for segment in command.split("|")]
    if not segments:
        return ShellRisk.CONFIRM

    risks = [_classify_segment(segment) for segment in segments]
    if any(risk == ShellRisk.DENY for risk in risks):
        return ShellRisk.DENY
    if all(risk == ShellRisk.ALLOW for risk in risks):
        return ShellRisk.ALLOW
    return ShellRisk.CONFIRM


def _classify_segment(segment: str) -> ShellRisk:
    for op in _CONFIRM_OPERATORS:
        if op in segment:
            return ShellRisk.CONFIRM

    tokens = _tokens(segment)
    if not tokens:
        return ShellRisk.CONFIRM

    first = _first_command_token(segment)
    if not first:
        return ShellRisk.CONFIRM
    if first in _CONFIRM_PREFIXES:
        return ShellRisk.CONFIRM
    if first == "git":
        return _classify_git(tokens)
    if first in {"python", "python3", "py"}:
        return _classify_python(tokens)
    if first in _READONLY_PREFIXES or first.startswith("get-"):
        return ShellRisk.ALLOW
    if first in _VERSION_COMMANDS and _is_version_probe(tokens[1:]):
        return ShellRisk.ALLOW
    return ShellRisk.CONFIRM


def _classify_git(tokens: list[str]) -> ShellRisk:
    subcommand = _first_non_option(tokens[1:])
    if not subcommand:
        return ShellRisk.ALLOW
    if subcommand in _GIT_READONLY_SUBCOMMANDS:
        return ShellRisk.ALLOW
    if subcommand == "config" and "--get" in tokens[1:]:
        return ShellRisk.ALLOW
    return ShellRisk.CONFIRM


def _classify_python(tokens: list[str]) -> ShellRisk:
    args = tokens[1:]
    if _is_version_probe(args):
        return ShellRisk.ALLOW
    if len(args) >= 2 and args[0] == "-m" and args[1] in _PYTHON_READONLY_MODULES:
        return ShellRisk.ALLOW
    return ShellRisk.CONFIRM


def _is_version_probe(args: list[str]) -> bool:
    return bool(args) and all(arg in _VERSION_FLAGS for arg in args)


def _first_non_option(args: list[str]) -> str:
    for arg in args:
        if not arg.startswith("-"):
            return arg
    return ""


def _tokens(segment: str) -> list[str]:
    return [
        token.strip("\"'").lower()
        for token in re.findall(r'"[^"]*"|\'[^\']*\'|\S+', segment)
    ]


def _first_command_token(segment: str) -> str:
    text = segment.strip()
    if not text:
        return ""
    if text.startswith("("):
        match = re.match(r"^\(\s*([a-zA-Z][\w.-]*)\b", text)
        if match:
            return match.group(1).lower()
    match = re.match(r"^&?\s*([a-zA-Z][\w.-]*)\b", text)
    if not match:
        return ""
    return match.group(1).lower()
