import subprocess
import sys
from pathlib import Path

SCANNER = Path(__file__).parents[1] / "scripts/check_publication.py"


def git(path, *args):
    subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)


def commit(path):
    git(
        path,
        "-c",
        "user.name=Synthetic Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "Synthetic scanner fixture",
    )


def test_removed_secret_is_still_detected_in_history(tmp_path):
    git(tmp_path, "init", "-q")
    file = tmp_path / "synthetic.txt"
    file.write_text("ghp_" + "X" * 30)
    git(tmp_path, "add", "synthetic.txt")
    commit(tmp_path)
    file.write_text("safe synthetic content")
    git(tmp_path, "add", "synthetic.txt")
    commit(tmp_path)
    result = subprocess.run(
        [sys.executable, str(SCANNER)], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode != 0 and "historical object" in result.stderr
    assert "X" * 30 not in result.stderr


def test_end_of_line_private_path_is_detected(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "synthetic.txt").write_text("/" + "Volumes/Storage")
    git(tmp_path, "add", "synthetic.txt")
    result = subprocess.run(
        [sys.executable, str(SCANNER)], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode != 0


def test_annotated_tag_secret_is_detected(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "synthetic.txt").write_text("safe synthetic content")
    git(tmp_path, "add", "synthetic.txt")
    commit(tmp_path)
    git(
        tmp_path,
        "-c",
        "user.name=Synthetic Test",
        "-c",
        "user.email=test@example.invalid",
        "tag",
        "-a",
        "synthetic",
        "-m",
        "ghp_" + "X" * 30,
    )
    result = subprocess.run(
        [sys.executable, str(SCANNER)], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode != 0 and "historical object" in result.stderr
    assert "X" * 30 not in result.stderr
