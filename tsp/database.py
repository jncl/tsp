# vim: set ts=4 sts=4 sw=4 et tw=0:

from __future__ import print_function

import os
import sys
import time

__all__ = ['Database']

try:
    from sqlite3 import dbapi2 as sqlite
    from sqlite3 import OperationalError
except ImportError:
    print('Please install pysqlite2.', file=sys.stderr)
    sys.exit(13)


BOOTSTRAP = [
    'CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, added_at INTEGER, run_at INTEGER, finished_at INTEGER, command TEXT, status INTEGER, result INTEGER, stdout TEXT, stderr TEXT, time_r REAL, time_u REAL, time_s REAL)',
    'CREATE INDEX IF NOT EXISTS IDX_tasks_command ON tasks (command)',
]

DB_PATH = os.path.expanduser('~/.local/share/tsp/tasks.db')


class DAL(object):
    def __del__(self):
        self.rollback()

    def __enter__(self):
        self.begin_transaction()
        return self

    def __exit__(self, type, value, tb):
        if tb is None:
            self.commit()
        else:
            self.rollback()

    def __init__(self):
        self.filename = DB_PATH
        self.db = self.connect()
        self.bootstrap()

    def begin_transaction(self):
        self.query('BEGIN TRANSACTION')

    def bootstrap(self):
        for query in BOOTSTRAP:
            self.query(query)

    def commit(self):
        self.db.commit()

    def connect(self):
        folder = os.path.dirname(self.filename)
        if not os.path.exists(folder):
            os.makedirs(folder)

        db = sqlite.connect(self.filename)
        db.isolation_level = None
        return db

    def insert(self, table, props):
        fields = []
        marks = []
        params = []

        for k, v in props.items():
            fields.append('`' + k + '`')
            marks.append('?')
            params.append(v)

        csep = lambda items: ', '.join(items)

        query = 'INSERT INTO `%s` (%s) VALUES (%s)' % (table, csep(fields), csep(marks))
        return self.query(query, params)

    def query(self, query, params=None):
        cur = self.db.cursor()

        args = [query]
        if params is not None:
            args.append(params)

        try:
            cur.execute(*args)
            if query.startswith('SELECT '):
                rows = cur.fetchall()
                names = [desc[0] for desc in cur.description]
                return [dict(zip(names, row)) for row in rows]
            elif query.startswith('INSERT '):
                return cur.lastrowid
            else:
                return cur.rowcount

        except:
            self.log_exception('failed SQL statement: %s, params: %s' % (query, params))
            raise

        finally:
            cur.close()

    def rollback(self):
        self.db.rollback()

    def update(self, table, props, conditions):
        parts = []
        params = []
        where = []

        for k, v in props.items():
            parts.append(k + ' = ?')
            params.append(v)

        if conditions:
            for k, v in conditions.items():
                where.append(k + ' = ?')
                params.append(v)

        query = 'UPDATE `%s` SET %s' % (table, ', '.join(parts))
        if where:
            query += ' WHERE %s' % ' AND '.join(where)

        return self.query(query, params)


class Database(DAL):
    def add_task(self, command):
        if not isinstance(command, (list, tuple)):
            raise ValueError('task command must be list of arguments')

        command = self.shell_escape(command)

        return self.insert('tasks', {
            'added_at': int(time.time()),
            'command': command,
            'status': 0,
        })

    def get_next_task(self):
        rows = self.query('SELECT id, command FROM tasks WHERE status = 0 ORDER BY id LIMIT 1')
        return rows[0] if rows else None

    def get_task(self, task_id):
        rows = self.query('SELECT * FROM tasks WHERE id = ?', [task_id])
        return rows[0] if rows else None

    def list_failed_tasks(self):
        return self.query('SELECT id, run_at, added_at, finished_at, command, status, result FROM tasks WHERE status = 2 AND result <> 0 ORDER BY id')

    def list_finished_tasks(self):
        return self.query('SELECT id, run_at, added_at, finished_at, command, status, result FROM tasks WHERE status = 2 AND result = 0 ORDER BY id')

    def list_last_tasks(self):
        return reversed(self.query('SELECT id, run_at, added_at, finished_at, command, status, result FROM tasks ORDER BY id DESC LIMIT 50'))

    def list_pending_tasks(self):
        return self.query('SELECT id, run_at, added_at, finished_at, command, status, result FROM tasks WHERE status = 0 ORDER BY id')

    def log_exception(self, msg):
        print(msg, file=sys.stderr)

    def purge(self):
        """Delete logs older than 1 week."""
        since = time.time() - 86400 * 7
        count = self.query('DELETE FROM tasks WHERE status = 2 AND added_at < ?', [since])
        return count

    def purge_pending(self):
        return self.query('DELETE FROM tasks WHERE status = 0')

    def replace_task(self, command):
        self.query('DELETE FROM tasks WHERE status = 0 AND command = ?', [command])
        return self.add_task(command)

    def reset_running(self):
        # TODO: email about unfinished tasks.
        self.query('UPDATE tasks SET status = 0 WHERE status = 1')

    def set_failed(self, task_id, msg, rtime=None, utime=None, stime=None):
        if not isinstance(task_id, int):
            raise ValueError('task_id must be an integer')

        # TODO: email.

        return self.update('tasks', {
            'status': 2,
            'stderr': msg,
            'result': -1,
            'finished_at': int(time.time()),
            'time_r': rtime,
            'time_u': utime,
            'time_s': stime,
        }, {
            'id': task_id,
        })

    def set_finished(self, task_id, rc, stdout, stderr, rtime=None, utime=None, stime=None):
        if not isinstance(task_id, int):
            raise ValueError('task_id must be an integer')

        return self.update('tasks', {
            'status': 2,
            'stdout': stdout,
            'stderr': stderr,
            'result': rc,
            'finished_at': int(time.time()),
            'time_r': rtime,
            'time_u': utime,
            'time_s': stime,
        }, {
            'id': task_id,
        })

    def set_running(self, task_id):
        if not isinstance(task_id, int):
            raise ValueError('task_id must be an integer')

        return self.update('tasks', {
            'status': 1,
            'run_at': int(time.time()),
        }, {
            'id': task_id,
        })

    def shell_escape(self, args):
        escape = lambda s: s if ' ' not in s else '"%s"' % s
        args = [escape(arg) for arg in args]
        return ' '.join(args)
