"""V2 texture filtering must not reveal RGB stored beneath zero alpha."""
from __future__ import annotations

import gc
import importlib
import json
from pathlib import Path
import tempfile
import unittest

import live2d
import numpy as np
import pygame
from OpenGL import GL
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = (ROOT / "Resources/v2/haru/haru.model.json",
           ROOT / "Resources/v2/kasumi2/kasumi2.model.json")
SIZE = 320


class V2TextureAlphaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.display.init()
        pygame.display.gl_set_attribute(pygame.GL_ALPHA_SIZE, 8)
        pygame.display.set_mode((SIZE, SIZE), pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN)
        if GL.glGetIntegerv(GL.GL_ALPHA_BITS) < 8:
            raise RuntimeError("The regression tests require an RGBA framebuffer")
        live2d.enableLog(False)
        live2d.init()
        live2d.glInit()
        cls.legacy = importlib.import_module("live2d.v2")
        cls.legacy.enableLog(False)
        cls.legacy.init()

    @classmethod
    def tearDownClass(cls) -> None:
        gc.collect()
        cls.legacy.dispose()
        live2d.glRelease()
        live2d.dispose()
        pygame.quit()

    def render(self, backend: str, sample: Path, rgba: np.ndarray,
               screen=None, multiply=None, face_only=False, scale=1.0) -> np.ndarray:
        # Keep fixtures self-contained: reuse only the sample moc and replace its
        # atlases with generated PNGs. No BanG Dream asset is needed by the test.
        config = json.loads(sample.read_text(encoding="utf-8"))
        model_path = (sample.parent / config["model"]).resolve()
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            # The legacy loader concatenates relative resource paths directly.
            (directory / "model.moc").write_bytes(model_path.read_bytes())
            texture = directory / "atlas.png"
            Image.fromarray(rgba).save(texture)
            config = {"model": "model.moc", "textures": ["atlas.png"] * len(config["textures"])}
            path = directory / "fixture.model.json"
            path.write_text(json.dumps(config, indent=2), encoding="utf-8")
            runtime = live2d if backend == "native" else self.legacy
            model = runtime.Model()
            loaded = False
            try:
                model.LoadModelJson(str(path))
                loaded = True
                model.Resize(SIZE, SIZE)
                model.SetAutoBlink(False)
                model.SetAutoBreath(False)
                model.SetScale(scale)
                for index, name in enumerate(model.GetPartIds()):
                    if face_only:
                        model.SetPartOpacity(index, float(name == "PARTS_01_FACE_001"))
                    if screen is not None:
                        model.SetPartScreenColor(index, *screen, 1.0)
                    if multiply is not None:
                        model.SetPartMultiplyColor(index, *multiply, 1.0)
                GL.glUseProgram(0)
                GL.glViewport(0, 0, SIZE, SIZE)
                GL.glDisable(GL.GL_SCISSOR_TEST)
                GL.glColorMask(True, True, True, True)
                GL.glClearColor(0, 0, 0, 0)
                GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
                model.Draw()
                GL.glFinish()
                pixels = GL.glReadPixels(0, 0, SIZE, SIZE, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
                self.assertEqual(GL.glGetError(), GL.GL_NO_ERROR)
                return np.frombuffer(pixels, dtype=np.uint8).reshape(SIZE, SIZE, 4).copy()
            finally:
                if loaded:
                    model.DestroyRenderer()
                del model
                gc.collect()

    def test_hidden_rgb_does_not_change_filtered_image(self) -> None:
        for backend in ("native", "python"):
            for sample in SAMPLES:
                # The low-resolution atlas forces both magnification and mipmap
                # filtering at different model scales, including clipped draws.
                for scale in (0.5, 1.7):
                    with self.subTest(backend=backend, sample=sample.parent.name, scale=scale):
                        original = np.empty((32, 32, 4), dtype=np.uint8)
                        original[:] = (224, 128, 64, 255)
                        original[:, 16:] = (76, 105, 113, 0)
                        alternate = original.copy()
                        alternate[:, 16:, :3] = (255, 0, 255)
                        a = self.render(backend, sample, original, scale=scale)
                        b = self.render(backend, sample, alternate, scale=scale)
                        self.assertGreater(int(a[:, :, 3].max()), 0)
                        np.testing.assert_array_equal(a, b)

    def test_screen_color_preserves_fully_transparent_pixels(self) -> None:
        transparent = np.full((8, 8, 4), (76, 105, 113, 0), dtype=np.uint8)
        for backend in ("native", "python"):
            for sample in SAMPLES:
                with self.subTest(backend=backend, sample=sample.parent.name):
                    frame = self.render(backend, sample, transparent, screen=(0.2, 0.3, 0.1))
                    self.assertEqual(int(frame.max()), 0)

    def test_partial_alpha_keeps_its_color(self) -> None:
        rgba = np.full((8, 8, 4), (224, 128, 64, 128), dtype=np.uint8)
        for backend in ("native", "python"):
            for screen, multiply in ((None, None), ((0.2, 0.3, 0.1), None),
                                     (None, (0.6, 0.8, 0.4)),
                                     ((0.2, 0.3, 0.1), (0.6, 0.8, 0.4))):
                with self.subTest(backend=backend, screen=screen, multiply=multiply):
                    frame = self.render(backend, SAMPLES[0], rgba, screen=screen,
                                        multiply=multiply, face_only=True)
                    alpha = frame[:, :, 3].astype(np.float32)
                    interior = alpha >= 120
                    self.assertGreater(int(interior.sum()), 100)
                    color = np.array((224, 128, 64), dtype=float) / 255
                    if multiply is not None:
                        color *= multiply
                    if screen is not None:
                        color += np.array(screen) * (1 - color)
                    expected = alpha[:, :, None] * color
                    # An extra alpha multiply would darken the interior by about 50%.
                    np.testing.assert_allclose(frame[:, :, :3][interior], expected[interior], atol=2)


if __name__ == "__main__":
    unittest.main()
