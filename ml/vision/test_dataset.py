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


def test_augment_only_train_keeps_session_and_boxes(tmp_path: Path) -> None:
    pil = pytest.importorskip("PIL.Image")
    raw = make_raw(tmp_path, {f"s{i}": 2 for i in range(10)})
    for f in (raw / "images").iterdir():
        pil.new("RGB", (64, 48), (200, 150, 90)).save(f, "JPEG")
    data = json.loads((raw / "annotations.json").read_text())
    for im, a in zip(data["images"], data["annotations"], strict=True):
        im.update(width=64, height=48)
        a["bbox"] = [20, 14, 24, 20]
    (raw / "annotations.json").write_text(json.dumps(data))

    m = dataset.split(raw, tmp_path / "v1", 42, augment_copies=2)
    assert dataset.check(tmp_path / "v1") == []
    assert m["augment_copies"] == 2
    train = json.loads((tmp_path / "v1" / "train" / "_annotations.coco.json").read_text())
    originals = [i for i in train["images"] if "augmented_from" not in i]
    copies = [i for i in train["images"] if "augmented_from" in i]
    assert len(copies) == 2 * len(originals)
    by_name = {i["file_name"]: i for i in originals}
    assert all(c["session"] == by_name[c["augmented_from"]]["session"] for c in copies)
    ids = {i["id"] for i in train["images"]}
    assert len(ids) == len(train["images"])
    assert all(a["image_id"] in ids and a["bbox"][2] > 0 and a["bbox"][3] > 0 for a in train["annotations"])
    for name in ("valid", "test"):
        split = json.loads((tmp_path / "v1" / name / "_annotations.coco.json").read_text())
        assert not any("augmented_from" in i for i in split["images"])
