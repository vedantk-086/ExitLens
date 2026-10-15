"""Helper functions to create realistic fixture repositories for scanner tests."""

from pathlib import Path


def create_standard_fixture_repo(base_dir: Path) -> Path:
    """Create a standard multi-manifest Python repository."""
    repo = base_dir / "standard_repo"
    repo.mkdir(parents=True, exist_ok=True)

    # 1. Base requirements.txt with recursive include and comments
    (repo / "requirements.txt").write_text(
        "# Core dependencies\n"
        "requests>=2.25.0, <3.0.0\n"
        "urllib3==1.26.15\n"
        "-r extra-requirements.txt\n"
        "colorama>=0.4.4; sys_platform == 'win32'\n",
        encoding="utf-8",
    )

    # 2. Included extra-requirements.txt
    (repo / "extra-requirements.txt").write_text(
        "pyyaml~=6.0\n"
        "click>=8.0.0\n",
        encoding="utf-8",
    )

    # 3. pyproject.toml with PEP 621 and Poetry sections
    (repo / "pyproject.toml").write_text(
        '[project]\n'
        'name = "standard-repo"\n'
        'version = "1.0.0"\n'
        'dependencies = [\n'
        '    "fastapi>=0.100.0",\n'
        '    "pydantic>=2.0.0",\n'
        ']\n\n'
        '[project.optional-dependencies]\n'
        'dev = ["pytest>=7.0.0", "black"]\n\n'
        '[tool.poetry.dependencies]\n'
        'python = "^3.12"\n'
        'httpx = ">=0.24.0"\n',
        encoding="utf-8",
    )

    # 4. setup.cfg
    (repo / "setup.cfg").write_text(
        "[metadata]\n"
        "name = standard-repo\n\n"
        "[options]\n"
        "install_requires =\n"
        "    tqdm>=4.60.0\n"
        "    packaging\n\n"
        "[options.extras_require]\n"
        "test =\n"
        "    pytest-mock\n",
        encoding="utf-8",
    )

    # 5. Python source code in src/
    src = repo / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "app.py").write_text(
        "import requests\n"
        "from urllib3.util import Retry\n"
        "import yaml\n"
        "from fastapi import FastAPI\n\n"
        "app = FastAPI()\n\n"
        "def fetch_data(url: str):\n"
        "    res = requests.get(url)\n"
        "    return yaml.safe_load(res.text)\n",
        encoding="utf-8",
    )

    # 6. Tests in tests/
    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_app.py").write_text(
        "import pytest\n"
        "import requests\n"
        "from src.app import fetch_data\n\n"
        "def test_fetch():\n"
        "    assert fetch_data is not None\n",
        encoding="utf-8",
    )

    # 7. Excluded directories to verify walker skips them
    venv_dir = repo / ".venv" / "lib" / "site-packages"
    venv_dir.mkdir(parents=True, exist_ok=True)
    (venv_dir / "dummy_dep.py").write_text("import hidden_in_venv\n", encoding="utf-8")

    git_dir = repo / ".git" / "objects"
    git_dir.mkdir(parents=True, exist_ok=True)
    (git_dir / "blob.py").write_text("import hidden_in_git\n", encoding="utf-8")

    return repo


def create_dynamic_and_malformed_fixture_repo(base_dir: Path) -> Path:
    """Create a repository containing dynamic setup.py, unsupported pip directives, and loops."""
    repo = base_dir / "dynamic_repo"
    repo.mkdir(parents=True, exist_ok=True)

    # 1. setup.py with dynamic expression
    (repo / "setup.py").write_text(
        "from setuptools import setup\n\n"
        "def parse_requirements():\n"
        "    return ['dynamic-pkg>=1.0']\n\n"
        "setup(\n"
        "    name='dynamic-repo',\n"
        "    version='0.1.0',\n"
        "    install_requires=parse_requirements(),\n"
        "    tests_require=['static-test-dep==1.2.3'],\n"
        ")\n",
        encoding="utf-8",
    )

    # 2. requirements.txt with unsupported directives (-c, -i, -e)
    (repo / "requirements.txt").write_text(
        "-c constraints.txt\n"
        "-i https://custom.pypi.org/simple\n"
        "-e .\n"
        "valid-pkg==2.0.0\n",
        encoding="utf-8",
    )

    # 3. Recursive circular loop: req_a -> req_b -> req_a
    (repo / "req_a.txt").write_text("-r req_b.txt\npkg-a==1.0\n", encoding="utf-8")
    (repo / "req_b.txt").write_text("-r req_a.txt\npkg-b==1.0\n", encoding="utf-8")

    # 4. Malformed Python syntax file
    (repo / "bad_syntax.py").write_text(
        "def broken_function(\n"
        "    print('Missing closing parenthesis'\n",
        encoding="utf-8",
    )

    return repo


def create_lockfiles_and_pipfile_fixture_repo(base_dir: Path) -> Path:
    """Create a repository containing Pipfile, Pipfile.lock, poetry.lock, and uv.lock."""
    repo = base_dir / "lockfile_repo"
    repo.mkdir(parents=True, exist_ok=True)

    # 1. Pipfile
    (repo / "Pipfile").write_text(
        '[[source]]\n'
        'url = "https://pypi.org/simple"\n'
        'verify_ssl = true\n'
        'name = "pypi"\n\n'
        '[packages]\n'
        'requests = ">=2.28.0"\n'
        'flask = "*"\n\n'
        '[dev-packages]\n'
        'pytest = ">=7.0.0"\n',
        encoding="utf-8",
    )

    # 2. Pipfile.lock
    (repo / "Pipfile.lock").write_text(
        '{\n'
        '  "_meta": {"hash": {"sha256": "abcdef"}},\n'
        '  "default": {\n'
        '    "requests": {"version": "==2.28.1"},\n'
        '    "flask": {"version": "==2.2.2"}\n'
        '  },\n'
        '  "develop": {\n'
        '    "pytest": {"version": "==7.1.3"}\n'
        '  }\n'
        '}\n',
        encoding="utf-8",
    )

    # 3. poetry.lock
    (repo / "poetry.lock").write_text(
        '[[package]]\n'
        'name = "requests"\n'
        'version = "2.28.1"\n'
        'category = "main"\n'
        'optional = false\n\n'
        '[[package]]\n'
        'name = "pytest"\n'
        'version = "7.1.3"\n'
        'category = "dev"\n'
        'optional = false\n',
        encoding="utf-8",
    )

    # 4. uv.lock
    (repo / "uv.lock").write_text(
        'version = 1\n'
        'revision = 1\n\n'
        '[[package]]\n'
        'name = "urllib3"\n'
        'version = "1.26.12"\n\n'
        '[[package]]\n'
        'name = "certifi"\n'
        'version = "2022.9.24"\n',
        encoding="utf-8",
    )

    return repo


def create_malformed_manifests_fixture_repo(base_dir: Path) -> Path:
    """Create a repository containing intentionally corrupted manifest files."""
    repo = base_dir / "malformed_manifests_repo"
    repo.mkdir(parents=True, exist_ok=True)

    # Corrupted pyproject.toml
    (repo / "pyproject.toml").write_text(
        "[project\nname = unclosed string\n",
        encoding="utf-8",
    )

    # Corrupted Pipfile
    (repo / "Pipfile").write_text(
        "[packages\nrequests = \n",
        encoding="utf-8",
    )

    # Corrupted Pipfile.lock
    (repo / "Pipfile.lock").write_text(
        "{ bad json: true, ",
        encoding="utf-8",
    )

    # Corrupted setup.cfg
    (repo / "setup.cfg").write_text(
        "[metadata\nunclosed section header",
        encoding="utf-8",
    )

    return repo

