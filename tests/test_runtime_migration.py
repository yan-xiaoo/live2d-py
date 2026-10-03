"""使用真实原生模型验证统一接口、呼吸补丁及最低 Python 版本。"""

from __future__ import annotations

import ast
import gc
import importlib
from pathlib import Path
import tempfile
import unittest

import live2d


ROOT = Path(__file__).resolve().parents[1]
MODELS = (
    ROOT / "Resources/v2/haru/haru.model.json",
    ROOT / "Resources/v3/Haru/Haru.model3.json",
)


class RuntimeMigrationTest(unittest.TestCase):
    """不创建渲染器，直接检查 V2/V3 原生行为。"""

    @classmethod
    def setUpClass(cls) -> None:
        """初始化框架并关闭原生日志。"""
        live2d.init()
        live2d.enableLog(False)

    @classmethod
    def tearDownClass(cls) -> None:
        """确认模型已释放后销毁框架。"""
        gc.collect()
        live2d.dispose()

    def load(self, index: int) -> live2d.Model:
        """加载指定 SDK 的样例模型，避免依赖窗口或 OpenGL。"""
        model = live2d.Model()
        model.LoadModelJson(str(MODELS[index]), create_renderer=False)
        return model

    def test_parameter_roundtrip_in_both_versions(self) -> None:
        """统一参数接口能按 ID 和索引读写，并保留参数元数据。"""
        for index in (0, 1):
            with self.subTest(version=index + 2):
                model = self.load(index)
                self.assertEqual(model.Version(), index + 2)
                ids = model.GetParamIds()
                self.assertEqual(len(ids), model.GetParamCount())
                model.SetParamById(ids[0], 7.5)
                self.assertAlmostEqual(model.GetParamValueByIndex(0), 7.5)
                self.assertAlmostEqual(model.GetParamValueById(ids[0]), 7.5)
                self.assertLess(model.GetParamMinByIndex(0), model.GetParamMaxByIndex(0))
                del model

    def test_breath_only_does_not_move_head(self) -> None:
        """仅呼吸参数模式保持头部静止，切回完整模式恢复头部摆动。"""
        for index in (0, 1):
            with self.subTest(version=index + 2):
                model = self.load(index)
                angle = "PARAM_ANGLE_X" if index == 0 else "ParamAngleX"
                model.SetParamById(angle, 0)
                model.SetAutoBreathParameterOnly(True)
                model.UpdateBreath(0.2)
                self.assertAlmostEqual(model.GetParamValueById(angle), 0)
                model.SetAutoBreath(False)
                model.SetAutoBreath(True)
                model.UpdateBreath(0.2)
                self.assertNotAlmostEqual(model.GetParamValueById(angle), 0)
                del model

    def test_v2_breath_uses_seconds_as_period(self) -> None:
        """V2 呼吸在 3.2345 秒后回到同一相位，四分之一周期达到峰值。"""
        model = self.load(0)
        model.SetAutoBreathParameterOnly(True)
        model.UpdateBreath(0)
        baseline = model.GetParamValueById("PARAM_BREATH")
        model.UpdateBreath(3.2345)
        self.assertAlmostEqual(model.GetParamValueById("PARAM_BREATH"), baseline, places=5)
        model.UpdateBreath(3.2345 / 4)
        self.assertAlmostEqual(model.GetParamValueById("PARAM_BREATH"), 1.0, places=5)

    def test_invalid_model_is_a_python_exception(self) -> None:
        """缺失或非法模型返回 Python 异常，不结束宿主进程。"""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "invalid.json"
            for text in (None, "{", "{}"):
                if text is not None:
                    path.write_text(text, encoding="utf-8")
                with self.subTest(text=text), self.assertRaises(ValueError):
                    live2d.Model().LoadModelJson(str(path), create_renderer=False)

    def test_package_syntax_and_legacy_v2_import(self) -> None:
        """解析所有分发源码，纯 Python V2 也能在最低版本中导入。"""
        for path in Path(live2d.__file__).parent.rglob("*.py"):
            with self.subTest(path=path):
                ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        importlib.import_module("live2d.v2")

    def test_reinitialize_framework_after_dispose(self) -> None:
        """窗口重新创建后可再次初始化同一个统一运行时。"""
        for _ in range(3):
            model = self.load(1)
            del model
            gc.collect()
            live2d.dispose()
            live2d.init()


if __name__ == "__main__":
    unittest.main()
