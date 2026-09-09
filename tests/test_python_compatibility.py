from __future__ import annotations

import ast
import contextlib
import importlib
import io
from pathlib import Path
import subprocess
import sys
import unittest


class PythonCompatibilityTest(unittest.TestCase):
    """验证最低版本语法、日志行为和原生绑定的异常传播。"""

    def test_package_syntax(self) -> None:
        """使用当前解释器解析所有随包分发的 Python 源文件。"""
        import live2d

        for path in Path(live2d.__file__).parent.rglob("*.py"):
            with self.subTest(path=path):
                ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))

    def test_v2_log_levels(self) -> None:
        """纯 Python v2 可以导入，日志级别切换保留原有输出。"""
        log = importlib.import_module("live2d.v2.core.util.log.__ut_log")
        old_level = log.getLogLevel()
        old_enabled = log.isLogEnabled()
        try:
            log.enableLog(True)
            for level, name in enumerate(("DEBUG", "INFO", "WARN", "ERROR")):
                with self.subTest(level=level):
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        log.setLogLevel(level)
                    self.assertEqual(log.getLogLevel(), level)
                    self.assertIn("[Log] Level=" + name, output.getvalue())
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                log.setLogLevel(99)
                log.enableLog(False)
                log.setLogLevel(0)
            self.assertEqual(output.getvalue(), "")
        finally:
            with contextlib.redirect_stdout(io.StringIO()):
                log.setLogLevel(old_level)
                log.enableLog(old_enabled)

    def test_parameter_import_error_is_preserved(self) -> None:
        """隔离缓存并模拟导入失败，确保绑定传播原异常而非 SystemError。"""
        code = '''
from __future__ import annotations
import live2d.v2cpp as live2d
from unittest.mock import patch

model = live2d.LAppModel()
with patch("builtins.__import__", side_effect=ImportError("parameter import failed")):
    try:
        model.GetParameter(0)
    except ImportError as error:
        assert str(error) == "parameter import failed"
    else:
        raise AssertionError("GetParameter did not propagate ImportError")
'''
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
