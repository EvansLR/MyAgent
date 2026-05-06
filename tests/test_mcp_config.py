from myagent.mcp import parse_mcp_servers


def test_parse_mcp_servers_reads_valid_servers() -> None:
    configs = parse_mcp_servers(
        {
            "mcpServers": {
                "demo": {
                    "command": "python",
                    "args": ["server.py"],
                    "env": {"TOKEN": "abc"},
                }
            }
        }
    )

    assert len(configs) == 1
    assert configs[0].name == "demo"
    assert configs[0].command == "python"
    assert configs[0].args == ["server.py"]
    assert configs[0].env == {"TOKEN": "abc"}


def test_parse_mcp_servers_reads_url_servers() -> None:
    configs = parse_mcp_servers(
        {
            "mcpServers": {
                "didi-mcp": {
                    "url": "https://example.test/mcp",
                }
            }
        }
    )

    assert len(configs) == 1
    assert configs[0].name == "didi-mcp"
    assert configs[0].url == "https://example.test/mcp"
    assert configs[0].command is None


def test_parse_mcp_servers_skips_invalid_entries() -> None:
    configs = parse_mcp_servers(
        {
            "mcpServers": {
                "missing-command": {},
                "not-object": "python",
            }
        }
    )

    assert configs == []
