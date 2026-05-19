from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "post_deploy_check.py"
    spec = spec_from_file_location("post_deploy_check", path)
    module = module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_root_contract_accepts_chinese_console_title() -> None:
    module = _load_module()
    body = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
      <title>PriceReader 控制台</title>
    </head>
    <body>
      <h1>PriceReader 控制台</h1>
    </body>
    </html>
    """
    assert module.root_contract_passed(body) is True


def test_root_contract_accepts_english_console_title() -> None:
    module = _load_module()
    body = """
    <!DOCTYPE html>
    <html>
    <head>
      <title>PriceReader Console</title>
    </head>
    <body>
      <h1>PriceReader Console</h1>
    </body>
    </html>
    """
    assert module.root_contract_passed(body) is True


def test_root_contract_rejects_unrelated_html() -> None:
    module = _load_module()
    body = """
    <!DOCTYPE html>
    <html>
    <head>
      <title>Swagger UI</title>
    </head>
    <body>
      <h1>Swagger UI</h1>
    </body>
    </html>
    """
    assert module.root_contract_passed(body) is False
