import json
from pathlib import Path

import pytest

import dataset


def make_raw(tmp: Path, sessions: dict[str, int]) -> Path:
    raw = tmp / "raw"
    (raw / "images").mkdir(parents=True)
    images, anns, n = [], [], 0
    for sess, count in sessions.items():
        for k in range(count):
            n += 1
            name = f"{sess}_{k}.jpg"
            (raw / "images" / name).write_bytes(f"img{n}".encode())
            images.append({"id": n, "file_name": name, "session": sess})
            anns.append({"id": n, "image_id": n, "category_id": 1, "bbox": [0, 0, 1, 1]})
    (raw / "annotations.json").write_text(
        json.dumps({"images": images, "annotations": anns, "categories": [{"id": 1, "name": "empanada"}]})
    )
    return raw


def test_sessions_never_split_across_sets(tmp_path: Path) -> None:
    sizes = {f"s{i}": 4 for i in range(10)}
    where = dataset.assign_sessions(sizes, seed=1)
    assert set(where) == set(sizes) and set(where.values()) == set(dataset.SPLITS)


def test_assignment_is_reproducible() -> None:
    sizes = {f"s{i}": i + 1 for i in range(12)}
    assert dataset.assign_sessions(sizes, 7) == dataset.assign_sessions(sizes, 7)


def test_split_then_check_ok_and_detects_tampering(tmp_path: Path) -> None:
    raw = make_raw(tmp_path, {f"s{i}": 3 for i in range(10)})
    out = tmp_path / "v1"
    m = dataset.split(raw, out, seed=42)
    assert sum(s["images"] for s in m["splits"].values()) == 30
    assert dataset.check(out) == []
    victim = next(out.glob("train/*.jpg"))
    victim.write_bytes(b"otra cosa")
    assert any("ALTERADO" in p for p in dataset.check(out))


def test_split_requires_session(tmp_path: Path) -> None:
    raw = make_raw(tmp_path, {"s": 2})
    data = json.loads((raw / "annotations.json").read_text())
    del data["images"][0]["session"]
    (raw / "annotations.json").write_text(json.dumps(data))
    with pytest.raises(SystemExit):
        dataset.split(raw, tmp_path / "v1", 1)


def test_version_is_not_overwritten(tmp_path: Path) -> None:
    raw = make_raw(tmp_path, {f"s{i}": 2 for i in range(6)})
    dataset.split(raw, tmp_path / "v1", 1)
    with pytest.raises(SystemExit):
        dataset.split(raw, tmp_path / "v1", 1)
