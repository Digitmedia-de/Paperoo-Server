import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / 'logs'
BACKUP_DIR = ROOT / 'backups'
STATUS_PATH = LOG_DIR / 'update-status.json'
LOCK_PATH = LOG_DIR / 'update.lock'


class UpdateError(Exception):
    pass


def run(command, capture_output=True):
    return subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def git(*arguments):
    return run(['git', *arguments]).stdout.strip()


def extract_version(source):
    match = re.search(r"^APP_VERSION\s*=\s*['\"]([^'\"]+)['\"]", source, re.MULTILINE)
    if not match:
        raise UpdateError('APP_VERSION was not found in app.py')
    return match.group(1)


def local_version():
    return extract_version((ROOT / 'app.py').read_text())


def update_check():
    local_commit = git('rev-parse', 'HEAD')
    git('fetch', '--quiet', 'origin', 'main')
    remote_commit = git('rev-parse', 'origin/main')
    remote_source = git('show', 'origin/main:app.py')
    behind = int(git('rev-list', '--count', 'HEAD..origin/main'))
    ahead = int(git('rev-list', '--count', 'origin/main..HEAD'))
    return {
        'success': True,
        'local_version': local_version(),
        'remote_version': extract_version(remote_source),
        'local_commit': local_commit,
        'remote_commit': remote_commit,
        'behind': behind,
        'ahead': ahead,
        'fast_forward_possible': ahead == 0,
        'update_available': behind > 0,
    }


def write_status(status, message, **details):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        'status': status,
        'message': message,
        'running': status in {'running', 'restarting'},
        'current_version': local_version(),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        **details,
    }
    temporary_path = STATUS_PATH.with_suffix('.tmp')
    temporary_path.write_text(json.dumps(payload, indent=2) + '\n')
    temporary_path.replace(STATUS_PATH)


def acquire_lock():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        LOCK_PATH.mkdir()
    except FileExistsError as error:
        raise UpdateError('Another update is already running') from error


def create_backup():
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    destination = BACKUP_DIR / timestamp
    destination.mkdir(parents=True, exist_ok=False)
    destination.chmod(0o700)

    env_path = ROOT / '.env'
    if env_path.exists():
        shutil.copy2(env_path, destination / '.env')

    database_path = ROOT / 'todos.db'
    database_backup = destination / 'todos.db'
    if database_path.exists():
        source = sqlite3.connect(database_path)
        target = sqlite3.connect(database_backup)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()

    (destination / 'backup.json').write_text(json.dumps({
        'commit': git('rev-parse', 'HEAD'),
        'version': local_version(),
        'created_at': datetime.now(timezone.utc).isoformat(),
    }, indent=2) + '\n')
    return destination, database_backup


def ensure_virtual_environment():
    if sys.version_info < (3, 11):
        raise UpdateError('Python 3.11 or newer is required')
    python = ROOT / 'venv' / 'bin' / 'python'
    if not python.exists():
        run([sys.executable, '-m', 'venv', str(ROOT / 'venv')])
    return python


def install(no_restart=False):
    acquire_lock()
    old_commit = None
    pulled = False
    migration_started = False
    database_backup = None
    try:
        if git('branch', '--show-current') != 'main':
            raise UpdateError('Updates must be installed from the main branch')
        if git('status', '--porcelain'):
            raise UpdateError('The working tree must be clean before updating')

        check = update_check()
        if not check['update_available']:
            write_status('success', 'The server is already up to date', **check)
            return check
        if not check['fast_forward_possible']:
            raise UpdateError('The local branch has diverged from origin/main')

        old_commit = check['local_commit']
        write_status('running', 'Creating a backup', target_version=check['remote_version'])
        backup_directory, database_backup = create_backup()

        write_status('running', 'Pulling origin/main', target_version=check['remote_version'])
        git('pull', '--ff-only', 'origin', 'main')
        pulled = True

        python = ensure_virtual_environment()
        write_status('running', 'Installing dependencies', target_version=check['remote_version'])
        run([str(python), '-m', 'pip', 'install', '-r', 'requirements.txt'], capture_output=False)
        run([str(python), '-m', 'pip', 'check'])
        run([str(python), '-m', 'compileall', '-q', 'app.py', 'modules'])

        if (ROOT / 'modules' / 'migrate.py').exists():
            migration_started = True
            write_status('running', 'Running database migrations', target_version=check['remote_version'])
            run([str(python), '-m', 'modules.migrate'], capture_output=False)

        if no_restart:
            write_status(
                'success',
                'Update installed without restarting the service',
                backup=str(backup_directory.relative_to(ROOT)),
                target_version=check['remote_version'],
            )
        else:
            if not shutil.which('systemctl'):
                raise UpdateError('systemctl is not available')
            LOCK_PATH.rmdir()
            write_status('restarting', 'Restarting Paperoo', target_version=check['remote_version'])
            command = ['systemctl', 'restart', 'paperoo']
            if hasattr(os, 'geteuid') and os.geteuid() != 0:
                if not shutil.which('sudo'):
                    raise UpdateError('sudo is required to restart Paperoo')
                command = ['sudo', '-n', *command]
            run(command)
            write_status(
                'success',
                'Update installed and Paperoo restarted',
                backup=str(backup_directory.relative_to(ROOT)),
                target_version=check['remote_version'],
            )
        current_commit = git('rev-parse', 'HEAD')
        return {
            'success': True,
            'local_version': local_version(),
            'remote_version': local_version(),
            'local_commit': current_commit,
            'remote_commit': current_commit,
            'update_available': False,
        }
    except Exception as error:
        if pulled and old_commit:
            try:
                git('reset', '--hard', old_commit)
                git('clean', '-fd')
                python = ROOT / 'venv' / 'bin' / 'python'
                if python.exists():
                    run([str(python), '-m', 'pip', 'install', '-r', 'requirements.txt'], capture_output=False)
            except Exception:
                pass
        if migration_started and database_backup and database_backup.exists():
            shutil.copy2(database_backup, ROOT / 'todos.db')
        write_status('failed', str(error))
        raise
    finally:
        if LOCK_PATH.exists():
            LOCK_PATH.rmdir()


def main():
    parser = argparse.ArgumentParser(description='Check and install Paperoo server updates')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--install', action='store_true')
    parser.add_argument('--no-restart', action='store_true')
    arguments = parser.parse_args()

    try:
        if arguments.check:
            result = update_check()
        else:
            result = install(arguments.no_restart)
        print(json.dumps(result))
        return 0
    except (UpdateError, subprocess.CalledProcessError, OSError, sqlite3.Error) as error:
        print(json.dumps({'success': False, 'error': str(error)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
