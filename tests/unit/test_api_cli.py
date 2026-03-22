from perpfut.cli import build_parser, main


def test_api_parser_defaults() -> None:
    parser = build_parser()

    args = parser.parse_args(["api"])

    assert args.command == "api"
    assert args.host == "127.0.0.1"
    assert args.port == 8000


def test_api_main_invokes_server(monkeypatch) -> None:
    captured = {}

    def fake_run_api_server(*, host: str, port: int) -> None:
        captured["host"] = host
        captured["port"] = port

    monkeypatch.setattr("perpfut.cli.run_api_server", fake_run_api_server)

    exit_code = main(["api", "--host", "127.0.0.1", "--port", "9000"])

    assert exit_code == 0
    assert captured == {"host": "127.0.0.1", "port": 9000}
