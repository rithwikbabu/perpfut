from perpfut.cli import build_parser


def test_api_parser_defaults() -> None:
    parser = build_parser()

    args = parser.parse_args(["api"])

    assert args.command == "api"
    assert args.host == "127.0.0.1"
    assert args.port == 8000
