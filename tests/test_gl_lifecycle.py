"""在真实 OpenGL 上下文中验证 V2/V3 混合绘制及重复创建窗口。"""

from __future__ import annotations

import gc
from pathlib import Path
import unittest

import live2d
import numpy as np
import pygame
from OpenGL import GL
from OpenGL.GL.shaders import compileProgram, compileShader


ROOT = Path(__file__).resolve().parents[1]
MODELS = (
    ROOT / "Resources/v2/haru/haru.model.json",
    ROOT / "Resources/v3/Haru/Haru.model3.json",
)


class GLLifecycleTest(unittest.TestCase):
    """检查渲染内容、调用方着色器状态及静态着色器释放。"""

    def test_mixed_models_and_recreated_contexts(self) -> None:
        """连续创建三次窗口，在每次窗口中交错绘制并释放两个版本的模型。"""
        pygame.init()
        try:
            for cycle in range(3):
                with self.subTest(cycle=cycle):
                    pygame.display.set_mode((400, 500), pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN)
                    live2d.init()
                    live2d.enableLog(False)
                    live2d.glInit()
                    program = compileProgram(
                        compileShader("#version 120\nvoid main(){gl_Position=gl_Vertex;}", GL.GL_VERTEX_SHADER),
                        compileShader("#version 120\nvoid main(){gl_FragColor=vec4(1.0);}", GL.GL_FRAGMENT_SHADER),
                    )
                    models: list[live2d.Model] = []
                    try:
                        for path in MODELS:
                            model = live2d.Model()
                            model.LoadModelJson(str(path))
                            model.Resize(400, 500)
                            model.SetAutoBlink(False)
                            model.SetAutoBreath(False)
                            models.append(model)
                        for _ in range(3):
                            for model in models:
                                GL.glUseProgram(program)
                                live2d.clearBuffer(0.9, 0.9, 0.9, 1.0)
                                model.Update(1.0 / 60)
                                model.Draw()
                                self.assertEqual(int(GL.glGetIntegerv(GL.GL_CURRENT_PROGRAM)), program)
                                pixels = GL.glReadPixels(0, 0, 400, 500, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
                                self.assertGreater(float(np.std(np.frombuffer(pixels, dtype=np.uint8))), 15)
                                self.assertEqual(GL.glGetError(), GL.GL_NO_ERROR)
                        # 销毁渲染器后可重新创建，静态着色器也可重复释放。
                        for model in models:
                            model.DestroyRenderer()
                        live2d.glRelease()
                        live2d.glRelease()
                        self.assertEqual(GL.glGetError(), GL.GL_NO_ERROR)
                        live2d.glInit()
                        for model in models:
                            model.CreateRenderer()
                            model.Draw()
                        self.assertEqual(GL.glGetError(), GL.GL_NO_ERROR)
                    finally:
                        for model in models:
                            model.DestroyRenderer()
                        models.clear()
                        del model
                        gc.collect()
                        GL.glUseProgram(0)
                        GL.glDeleteProgram(program)
                        live2d.glRelease()
                        self.assertEqual(GL.glGetError(), GL.GL_NO_ERROR)
                        live2d.dispose()
                        pygame.display.quit()
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()
