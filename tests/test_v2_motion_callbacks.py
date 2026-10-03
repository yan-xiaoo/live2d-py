"""验证 V2 在统一接口下的动作解析、取消及每次播放的回调归属。"""

from __future__ import annotations

import gc
from pathlib import Path
import tempfile
import unittest
import weakref

import live2d


class Callback:
    """通过弱引用观测原生播放记录持有的 Python 回调。"""

    def __init__(self, events: list[str], label: str) -> None:
        """保存事件目标与本次播放标识。"""
        self.events = events
        self.label = label

    def __call__(self, group: str, index: int) -> None:
        """记录对应播放的通知。"""
        self.events.append(self.label)


class V2MotionCallbackTest(unittest.TestCase):
    """以真实 Haru 模型和带控制字段的 MTN 验证原生运行时。"""

    @classmethod
    def setUpClass(cls) -> None:
        """初始化不依赖窗口的统一框架。"""
        live2d.init()
        live2d.enableLog(False)

    @classmethod
    def tearDownClass(cls) -> None:
        """在释放所有模型后销毁统一框架。"""
        gc.collect()
        live2d.dispose()

    def setUp(self) -> None:
        """加载独立模型和包含大小写、引号及逐参数淡入元数据的动作。"""
        self.folder: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        path = Path(self.folder.name) / "probe.mtn"
        path.write_text("'$fps=20\n$fadein=0\n$FadeOut=0\nFADEIN:PARAM_ANGLE_X=999\nPARAM_ANGLE_X=0,5,10,0\n")
        self.model: live2d.Model = live2d.Model()
        sample = Path(__file__).resolve().parents[1] / "Resources/v2/haru/haru.model.json"
        self.model.LoadModelJson(str(sample), create_renderer=False)
        self.model.LoadExtraMotion("probe", str(path))
        self.events: list[str] = []

    def tearDown(self) -> None:
        """清空队列，释放模型和临时动作文件。"""
        self.model.StopAllMotions()
        del self.model
        gc.collect()
        self.folder.cleanup()

    def start(self, label: str, priority: int = 3) -> tuple[weakref.ReferenceType[Callback], weakref.ReferenceType[Callback]]:
        """交出回调的唯一强引用，返回用于观察的弱引用。"""
        start, finish = Callback(self.events, label + "-start"), Callback(self.events, label + "-finish")
        refs = weakref.ref(start), weakref.ref(finish)
        self.model.StartMotion("probe", 0, priority, start, finish)
        return refs

    def advance(self, steps: int = 40) -> None:
        """以固定步长推进动作到自然结束。"""
        for _ in range(steps):
            self.model.Update(0.01)

    def test_overlapping_motion_keeps_callback_identity(self) -> None:
        """重复播放同一缓存曲线仍分别通知并释放每次播放的回调。"""
        first = self.start("a")
        self.advance(4)
        second = self.start("b")
        self.advance()
        self.assertEqual(self.events, ["a-start", "b-start", "a-finish", "b-finish"])
        self.assertTrue(all(ref() is None for ref in first + second))

    def test_stop_does_not_report_natural_finish(self) -> None:
        """取消立即释放回调，后续更新不再发送自然结束事件。"""
        refs = self.start("a")
        self.advance(1)
        self.model.StopAllMotions()
        self.assertTrue(all(ref() is None for ref in refs))
        self.advance()
        self.assertEqual(self.events, ["a-start"])

    def test_priority_rejection_preserves_active_playback(self) -> None:
        """被拒绝的低优先级请求不覆盖活动动作的回调。"""
        refs = self.start("a")
        rejected = self.start("rejected", priority=1)
        self.assertTrue(all(ref() is None for ref in rejected))
        self.advance()
        self.assertEqual(self.events, ["a-start", "a-finish"])
        self.assertTrue(all(ref() is None for ref in refs))

    def test_start_callback_can_replace_queue(self) -> None:
        """开始通知中停止并重播不会破坏队列遍历。"""
        def restart(group: str, index: int) -> None:
            """在开始通知中用另一播放替换当前队列。"""
            self.model.StopAllMotions()
            self.start("b")
        self.model.StartMotion("probe", 0, 3, restart, Callback(self.events, "cancelled"))
        self.advance()
        self.assertEqual(self.events, ["b-start", "b-finish"])

    def test_granular_update_dispatches_finish(self) -> None:
        """独立 UpdateMotion 入口也分发自然完成通知。"""
        refs = self.start("a")
        for _ in range(40):
            self.model.UpdateMotion(0.01)
        self.assertEqual(self.events, ["a-start", "a-finish"])
        self.assertTrue(all(ref() is None for ref in refs))

    def test_mtn_fps_and_control_fields(self) -> None:
        """带引号的 20 FPS 被识别，淡入元数据不会生成模型参数。"""
        self.start("a")
        self.advance(11)
        self.assertFalse(self.model.IsMotionFinished())
        self.advance(6)
        self.assertTrue(self.model.IsMotionFinished())
        self.assertNotIn("FADEIN:PARAM_ANGLE_X", self.model.GetParamIds())


if __name__ == "__main__":
    unittest.main()
