"""无窗口验证 v3 每次播放的回调归属、引用释放和回调重入。"""

from __future__ import annotations

import gc
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import weakref

import live2d.v3 as live2d


class Callback:
    """可弱引用的回调，用于检测原生层漏引用及过早释放。"""

    def __init__(self, events: list[str], label: str) -> None:
        """保存事件列表和本次播放的标签。"""
        self.events = events
        self.label = label

    def __call__(self, group: str, index: int) -> None:
        """记录实际收到的动作身份。"""
        self.events.append(f"{self.label}:{group}:{index}")


class MotionCallbackTest(unittest.TestCase):
    """直接测试安装的扩展，使用仓库 Haru moc3 和临时动作数据。"""

    folder: Path
    temporary: tempfile.TemporaryDirectory[str]
    model: live2d.Model
    events: list[str]

    @classmethod
    def setUpClass(cls) -> None:
        """准备无纹理模型并初始化一次 Cubism。"""
        cls.temporary = tempfile.TemporaryDirectory(prefix="live2d-callback-test-")
        cls.folder = Path(cls.temporary.name)
        moc = Path(__file__).resolve().parents[1] / "Resources/v3/Haru/Haru.moc3"
        shutil.copyfile(moc, cls.folder / "model.moc3")
        (cls.folder / "model.model3.json").write_text(json.dumps({
            "Version": 3, "FileReferences": {"Moc": "model.moc3"},
        }, indent=2) + "\n", encoding="utf-8")
        live2d.init()

    @classmethod
    def tearDownClass(cls) -> None:
        """先结束所有模型再释放框架和临时文件。"""
        gc.collect()
        live2d.dispose()
        cls.temporary.cleanup()

    def setUp(self) -> None:
        """每例使用独立的原生模型和回调事件列表。"""
        self.model = live2d.Model()
        self.model.LoadModelJson(str(self.folder / "model.model3.json"))
        self.events = []
        self.load_motion("probe")

    def tearDown(self) -> None:
        """清空剩余队列，避免例间残留回调。"""
        if hasattr(self, "model"):
            self.model.StopAllMotions()
            del self.model
        gc.collect()

    def load_motion(self, group: str, duration: float = 0.25, fade: float = 1.0) -> int:
        """生成能被原生解析器接受的简单参数曲线。"""
        path = self.folder / f"{group}.motion3.json"
        path.write_text(json.dumps({
            "Version": 3,
            "Meta": {"Duration": duration, "Fps": 30, "Loop": False,
                     "FadeInTime": 0, "FadeOutTime": fade,
                     "AreBeziersRestricted": True, "CurveCount": 1,
                     "TotalSegmentCount": 1, "TotalPointCount": 2,
                     "UserDataCount": 0, "TotalUserDataSize": 0},
            "Curves": [{"Target": "Parameter", "Id": "ParamAngleX",
                        "Segments": [0, 0, 0, duration, 10]}],
            "UserData": [],
        }, indent=2) + "\n", encoding="utf-8")
        return self.model.LoadExtraMotion(group, str(path))

    def start(self, label: str, group: str = "probe", priority: int = 3,
              random: bool = False) -> tuple[weakref.ReferenceType[Callback], weakref.ReferenceType[Callback]]:
        """把回调的唯一强引用交给扩展，并返回观察其生命周期的弱引用。"""
        start = Callback(self.events, label + "-start")
        finish = Callback(self.events, label + "-finish")
        refs = weakref.ref(start), weakref.ref(finish)
        if random:
            self.model.StartRandomMotion(group, priority, start, finish)
        else:
            self.model.StartMotion(group, 0, priority, start, finish)
        return refs

    def advance(self, count: int = 40) -> None:
        """以固定步长更新，避免依赖真实时间及 UI 定时器。"""
        for _ in range(count):
            self.model.Update(0.01)

    def assert_released(self, refs: tuple[weakref.ReferenceType[Callback], ...]) -> None:
        """确认原生层不再持有已结束或已取消播放的回调。"""
        gc.collect()
        self.assertTrue(all(ref() is None for ref in refs))

    def test_overlapping_same_motion_keeps_callback_identity(self) -> None:
        """旧播放自然结束时只能调用自己的回调，不能释放后一次的回调。"""
        first = self.start("a")
        self.advance(6)
        second = self.start("b")
        self.advance(40)
        self.assertEqual(self.events, ["a-start:probe:0", "b-start:probe:0",
                                      "a-finish:probe:0", "b-finish:probe:0"])
        self.assert_released(first + second)

    def test_two_requests_before_first_update(self) -> None:
        """同帧启动同一动作也必须分别触发开始及结束回调。"""
        first, second = self.start("a"), self.start("b")
        self.advance()
        self.assertCountEqual(self.events, ["a-start:probe:0", "b-start:probe:0",
                                           "a-finish:probe:0", "b-finish:probe:0"])
        self.assert_released(first + second)

    def test_single_motion_releases_each_callback(self) -> None:
        """开始回调执行后释放，结束回调保留到实际结束。"""
        refs = self.start("a")
        self.advance(1)
        self.assertIsNone(refs[0]())
        self.assertIsNotNone(refs[1]())
        self.advance()
        self.assert_released(refs)

    def test_stop_before_first_frame(self) -> None:
        """未开始就取消的播放不回调且立即释放所有引用。"""
        refs = self.start("a")
        self.model.StopAllMotions()
        self.assertEqual(self.events, [])
        self.assert_released(refs)

    def test_stop_after_start(self) -> None:
        """主动停止不伪造自然完成事件。"""
        refs = self.start("a")
        self.advance(1)
        self.model.StopAllMotions()
        self.advance()
        self.assertEqual(self.events, ["a-start:probe:0"])
        self.assert_released(refs)

    def test_priority_rejection_releases_callbacks(self) -> None:
        """低优先级请求被拒绝时不泄漏回调。"""
        self.start("a")
        refs = self.start("rejected", priority=1)
        self.assert_released(refs)
        self.advance()
        self.assertEqual(self.events, ["a-start:probe:0", "a-finish:probe:0"])

    def test_unknown_random_group_releases_callbacks(self) -> None:
        """随机动作组不存在时也要释放本次请求的引用。"""
        refs = self.start("missing", group="missing", random=True)
        self.assert_released(refs)
        self.assertEqual(self.events, [])

    def test_random_motion_uses_per_playback_callbacks(self) -> None:
        """随机动作入口采用同一套每次播放的回调管理。"""
        first, second = self.start("a", random=True), self.start("b", random=True)
        self.advance()
        self.assertCountEqual(self.events, ["a-start:probe:0", "b-start:probe:0",
                                           "a-finish:probe:0", "b-finish:probe:0"])
        self.assert_released(first + second)

    def test_missing_motion_keeps_immediate_callback_behavior(self) -> None:
        """兼容旧 API 对无文件动作的立即开始和结束通知。"""
        refs = self.start("missing", group="missing")
        self.assertEqual(self.events, ["missing-start:missing:0", "missing-finish:missing:0"])
        self.assert_released(refs)

    def test_fadeout_releases_without_natural_finish(self) -> None:
        """提前淡出的动作释放回调但不冒充自然结束。"""
        self.load_motion("long", duration=2, fade=0.01)
        first = self.start("a", group="long")
        self.advance(1)
        second = self.start("b")
        self.advance()
        self.assertEqual(self.events, ["a-start:long:0", "b-start:probe:0", "b-finish:probe:0"])
        self.assert_released(first + second)

    def test_model_destruction_releases_pending_callbacks(self) -> None:
        """销毁模型会取消尚未更新的队列项并释放回调。"""
        refs = self.start("a")
        del self.model
        self.assert_released(refs)
        self.assertEqual(self.events, [])

    def test_start_callback_can_stop_and_restart(self) -> None:
        """开始回调中清空队列并启动新动作不会破坏队列遍历。"""
        def restart(group: str, index: int) -> None:
            """在开始事件中替换当前播放。"""
            self.events.append("restart")
            self.model.StopAllMotions()
            self.start("b")

        self.model.StartMotion("probe", 0, 3, restart, Callback(self.events, "cancelled"))
        self.advance()
        self.assertEqual(self.events, ["restart", "b-start:probe:0", "b-finish:probe:0"])

    def test_finish_callback_can_restart_and_update(self) -> None:
        """结束回调可再次播放并重入更新，当前通知不得重复。"""
        def restart(group: str, index: int) -> None:
            """在完成通知内启动并更新下一次播放。"""
            self.events.append("restart")
            self.start("b")
            self.model.Update(0.01)

        self.model.StartMotion("probe", 0, 3, None, restart)
        self.advance(70)
        self.assertEqual(self.events, ["restart", "b-start:probe:0", "b-finish:probe:0"])

    def test_nested_update_completes_new_playback(self) -> None:
        """重入更新中已结束的新播放仍须在下次分发时收到通知。"""
        def restart(group: str, index: int) -> None:
            """在完成通知内把新播放直接更新到结束。"""
            self.start("b")
            self.advance()

        self.model.StartMotion("probe", 0, 3, None, restart)
        self.advance(70)
        self.assertEqual(self.events, ["b-start:probe:0", "b-finish:probe:0"])

    def test_stop_releases_callbacks_before_finalizer_reentry(self) -> None:
        """回调对象析构时启动动作也不会写入尚在删除的旧队列。"""
        model = self.model
        events = self.events

        class RestartOnDelete:
            """取消释放时重入动作入口的回调对象。"""

            def __call__(self, group: str, index: int) -> None:
                """记录不应收到的完成通知。"""
                events.append("unexpected")

            def __del__(self) -> None:
                """在对象释放时启动下一次播放。"""
                model.StartMotion("probe", 0, 3, None, Callback(events, "next"))

        callback = RestartOnDelete()
        reference = weakref.ref(callback)
        self.model.StartMotion("probe", 0, 3, None, callback)
        del callback
        self.model.StopAllMotions()
        self.assertIsNone(reference())
        self.advance()
        self.assertEqual(self.events, ["next:probe:0"])

    def test_playback_updates_parameters(self) -> None:
        """新增播放实例仍正确应用动作曲线，不能只让回调测试通过。"""
        self.load_motion("linear", fade=0)
        self.model.StartMotion("linear", 0, 3)
        self.model.UpdateMotion(0.01)
        self.model.UpdateMotion(0.125)
        # Haru 的首个参数是 ParamAngleX；曲线从 0 到 10 线性变化。
        self.assertAlmostEqual(self.model.GetParameterValue(0), 5.0, places=4)

    def test_cancel_suppresses_other_pending_notifications(self) -> None:
        """同一帧的早期回调取消队列后，其余通知不应继续执行。"""
        def cancel(group: str, index: int) -> None:
            """取消包含其它待分发回调的队列。"""
            self.model.StopAllMotions()

        self.model.StartMotion("probe", 0, 3, cancel)
        refs = self.start("b")
        self.advance()
        self.assertEqual(self.events, [])
        self.assert_released(refs)

    def test_invalid_callback_raises_type_error_without_retaining_other(self) -> None:
        """先验证两个回调，再取得引用，避免异常残留或部分引用泄漏。"""
        callback = Callback(self.events, "unused")
        before = sys.getrefcount(callback)
        for method, args in ((self.model.StartMotion, ("probe", 0, 3)),
                             (self.model.StartRandomMotion, ("probe", 3))):
            with self.assertRaises(TypeError):
                method(*args, callback, object())
            self.assertEqual(sys.getrefcount(callback), before)
        self.assertTrue(self.model.IsMotionFinished())

    def test_callback_exception_is_reported_without_poisoning_update(self) -> None:
        """回调异常报告给 unraisablehook，不让后续更新变成 SystemError。"""
        errors: list[object] = []

        def fail(group: str, index: int) -> None:
            """制造可识别的回调错误。"""
            raise ValueError("callback failure")

        with patch.object(sys, "unraisablehook", errors.append):
            self.model.StartMotion("probe", 0, 3, fail, Callback(self.events, "finish"))
            self.advance()
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(getattr(errors[0], "exc_value"), ValueError)
        self.assertEqual(self.events, ["finish:probe:0"])

    def test_update_motion_entry_point(self) -> None:
        """细粒度 UpdateMotion 入口也分发和释放回调。"""
        refs = self.start("a")
        for _ in range(40):
            self.model.UpdateMotion(0.01)
        self.assertEqual(self.events, ["a-start:probe:0", "a-finish:probe:0"])
        self.assert_released(refs)

    def test_repeated_overlap_releases_all_callbacks(self) -> None:
        """密集重复播放不会串用回调或积累引用。"""
        refs: list[weakref.ReferenceType[Callback]] = []
        for index in range(100):
            refs.extend(self.start(str(index)))
            self.advance(1)
        self.advance()
        self.assertEqual(len(self.events), 200)
        self.assertEqual(len(set(self.events)), 200)
        self.assert_released(tuple(refs))


if __name__ == "__main__":
    unittest.main()
