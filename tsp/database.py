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
    'CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, added_at INTEGER, run_at INTEGER, command TEXT, status INTEGER, result INTEGER, stdout TEXT, stderr TEXT, time_r REAL, time_u REAL, time_s REAL)',
    'CREATE INDEX IF NOT EXISTS IDX_tasks_command ON tasks (command)',
]

DB_PATH = os.path.expanduser('~/.local/share/tsp/tasks.db')


class Database(object):
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

    def add_task(self, command):
        if not isinstance(command, (list, tuple)):
            raise ValueError('task command must be list of arguments')

        command = self.shell_escape(command)

        return self.insert('tasks', {
            'added_at': int(time.time()),
            'command': command,
            'status': 0,
        })

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

    def list_pending_tasks(self):
        return self.query('SELECT id, command FROM tasks WHERE status = 0 ORDER BY id')

    def log_exception(self, msg):
        print(msg, file=sys.stderr)

    def purge(self):
        """Delete logs older than 1 week."""
        since = time.time() - 86400 * 7
        count = self.query('DELETE FROM tasks WHERE status = 2 AND added_at < ?', [since])
        return count

    def query(self, query, params=None):
        cur = self.db.cursor()

        args = [query]
        if params is not None:
            args.append(params)

        try:
            cur.execute(*args)
            if query.startswith('SELECT '):
                return cur.fetchall()
            elif query.startswith('INSERT '):
                return cur.lastrowid
            else:
                return cur.rowcount

        except:
            self.log_exception('failed SQL statement: %s, params: %s' % (query, params))
            raise

        finally:
            cur.close()

    def replace_task(self, command):
        self.query('DELETE FROM tasks WHERE status = 0 AND command = ?', [command])
        return self.add_task(command)

    def rollback(self):
        self.db.rollback()

    def shell_escape(self, args):
        escape = lambda s: s if ' ' not in s else '"%s"' % s
        args = [escape(arg) for arg in args]
        return ' '.join(args)
