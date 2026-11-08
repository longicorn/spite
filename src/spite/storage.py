"""Persistent, immutable forecast runs stored under a user-selected root."""
import json
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
MODEL_VERSION = '1'


def load_run(root, run_id, command):
    if not re.fullmatch(r'[0-9a-f]{32}', run_id):
        raise ValueError('Run ID must be 32 lowercase hexadecimal characters')
    path = Path(root) / command / run_id / 'snapshot.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ValueError(f'Cannot read snapshot {path}: {exc}') from exc
    if not isinstance(data, dict) or data.get('schema_version') != SCHEMA_VERSION or data.get('model_version') != MODEL_VERSION or data.get('command') != command or data.get('run_id') != run_id:
        raise ValueError(f'Unsupported or incompatible snapshot: {path}')
    return data


def save_run(root, command, snapshot, report, image_writer=None):
    parent = Path(root) / command
    parent.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    destination = parent / run_id
    temp = Path(tempfile.mkdtemp(prefix='.run-', dir=parent))
    try:
        snapshot = dict(snapshot, schema_version=SCHEMA_VERSION, model_version=MODEL_VERSION,
                        command=command, run_id=run_id,
                        created_at=datetime.now(timezone.utc).isoformat())
        (temp / 'report.md').write_text(report, encoding='utf-8')
        (temp / 'snapshot.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        if image_writer:
            image_writer(temp / 'chart.png')
        os.rename(temp, destination)
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return destination, run_id
