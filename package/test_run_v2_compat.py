"""使用真实 OpenGL 上下文验证 v2 模型、参数枚举及动作播放。"""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys
import time

import glfw
import numpy as np
from OpenGL import GL
from PIL import Image


def main() -> None:
    """加载指定模型并验证参数、动画变化和非空渲染结果。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--backend", choices=("v2cpp", "v2"), default="v2cpp")
    parser.add_argument("--motion", default="happiness")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    live2d = importlib.import_module("live2d." + args.backend)
    assert glfw.init(), "GLFW initialization failed"
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    window = glfw.create_window(500, 700, "Python compatibility test", None, None)
    assert window, "OpenGL context creation failed"
    glfw.make_context_current(window)
    try:
        live2d.init()
        live2d.glInit()
        live2d.enableLog(False)
        model = live2d.LAppModel()
        model.LoadModelJson(str(args.model.resolve()))
        model.Resize(500, 700)
        model.SetAutoBlinkEnable(False)
        model.SetAutoBreathEnable(False)
        count = model.GetParameterCount()
        assert count > 0, "Model has no parameters"
        parameters = [model.GetParameter(index) for index in range(count)]
        assert all(isinstance(param, live2d.Parameter) for param in parameters)
        assert all(param.id and param.min <= param.max for param in parameters)
        assert all(
            np.isfinite([param.value, param.min, param.max, param.default]).all()
            for param in parameters
        )
        if args.backend == "v2cpp":
            assert not any(
                name == "live2d.v2" or name.startswith("live2d.v2.")
                for name in sys.modules
            ), "v2cpp unexpectedly imported the pure-Python v2 engine"
        width, height = glfw.get_framebuffer_size(window)
        GL.glViewport(0, 0, width, height)
        live2d.clearBuffer()
        model.Update()
        model.Draw()
        first = bytes(GL.glReadPixels(0, 0, width, height, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE))
        baseline = [model.GetParameter(index).value for index in range(count)]
        model.StartMotion(args.motion, 0, live2d.MotionPriority.FORCE)
        assert not model.IsMotionFinished(), "Motion did not start"
        changed = False
        for _ in range(120):
            time.sleep(1 / 60)
            glfw.poll_events()
            live2d.clearBuffer()
            model.Update()
            model.Draw()
            changed = changed or any(
                abs(model.GetParameter(index).value - baseline[index]) > 1e-5
                for index in range(count)
            )
        pixels = bytes(GL.glReadPixels(0, 0, width, height, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE))
        rgba = np.frombuffer(pixels, dtype=np.uint8).reshape(height, width, 4)
        nonempty = int(np.count_nonzero(rgba[:, :, 3]))
        assert nonempty > 100, "Model rendered an empty image"
        assert changed, "Motion did not change model parameters"
        assert pixels != first, "Motion did not change the rendered image"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(np.flipud(rgba)).save(args.output)
        print(json.dumps({
            "python": sys.version.split()[0],
            "backend": args.backend,
            "module": live2d.__file__,
            "parameters": count,
            "motion": args.motion,
            "frames": 120,
            "parameters_changed": changed,
            "nontransparent_pixels": nonempty,
            "screenshot": str(args.output.resolve()),
        }, ensure_ascii=False))
        del model
        live2d.dispose()
    finally:
        glfw.destroy_window(window)
        glfw.terminate()


if __name__ == "__main__":
    main()
