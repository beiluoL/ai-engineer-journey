from __future__ import annotations

import sys

from ie.paths import P06_SRC, P08_SRC, P09_MODELS, P09_ROOT, ensure_deps_importable, ensure_models_dir


def test_dependency_paths_exist():
    p06, p08 = ensure_deps_importable()
    assert p06 == P06_SRC and p06.is_dir()
    assert p08 == P08_SRC and p08.is_dir()


def test_dependency_paths_are_importable():
    ensure_deps_importable()
    assert str(P06_SRC) in sys.path
    assert str(P08_SRC) in sys.path


def test_paths_are_relative_to_project_tree():
    assert P06_SRC.parent.parent == P09_ROOT.parent
    assert P08_SRC.parent.parent == P09_ROOT.parent


def test_models_directory_is_inside_p09():
    assert ensure_models_dir() == P09_MODELS
    assert P09_ROOT in P09_MODELS.parents
