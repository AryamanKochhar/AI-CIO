"""A shared development database must never leak into test configuration."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def _settings_probe(env_file: Path, *, testing: bool) -> dict:
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(('OPENAI_', 'OPEN_API_', 'OPENROUTER_'))}
    environment.update(PYTHONPATH=str(ROOT / 'apps/api'), AICIO_ENV_FILE=str(env_file),
                       DATABASE_URL='postgresql://localhost/isolated_test')
    if testing:
        environment['AICIO_TESTING'] = '1'
    else:
        environment.pop('AICIO_TESTING', None)
    code = ('import json; from ai_cio import settings as s; '
            'print(json.dumps(dict(database=s.DATABASE_URL, key=s.OPENAI_API_KEY, '
            'model=s.OPENAI_MODEL, instrument=str(s.INSTRUMENT_PATH))))')
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT.parent,
                            env=environment, text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def test_tests_do_not_load_developer_database_or_provider_secrets(tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('DATABASE_URL=postgresql://shared.invalid/postgres\n'
                        'OPENAI_API_KEY=fake-development-secret\nOPENAI_MODEL=development-model\n')
    output = _settings_probe(env_file, testing=True)
    assert output['database'] == 'postgresql://localhost/isolated_test'
    assert output['key'] == ''
    assert output['model'] != 'development-model'


def test_explicit_process_configuration_wins_and_relative_paths_resolve(tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('DATABASE_URL=postgresql://shared.invalid/postgres\n'
                        'OPENAI_MODEL=development-model\nINSTRUMENT_PATH=instruments/v1.0.json\n')
    output = _settings_probe(env_file, testing=False)
    assert output['database'] == 'postgresql://localhost/isolated_test'
    assert output['model'] == 'development-model'
    assert Path(output['instrument']) == ROOT / 'instruments/v1.0.json'
