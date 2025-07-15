# pylint: disable=logging-fstring-interpolation
# vim: set ts=4 sts=4 sw=4 et tw=0:
""" Database functions"""

import logging
import os
import time

from sqlite3 import dbapi2 as sqlite
from tsp.email import Email

logger = logging.getLogger(__name__)

__all__ = ['Database']


BOOTSTRAP = [
    'CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, added_at INTEGER, run_at INTEGER,\
        finished_at INTEGER, command TEXT, status INTEGER, result INTEGER, stdout TEXT,\
        stderr TEXT, time_r REAL, time_u REAL, time_s REAL)',
    'CREATE INDEX IF NOT EXISTS IDX_tasks_command ON tasks (command)',
]

DB_PATH = os.path.expanduser('~/.local/share/tsp/tasks.db')


class DAL:
    """ Database Abstraction Layer """
    def __del__(self):
        self.rollback()

    def __enter__(self):
        self.begin_transaction()
        return self

    def __exit__(self, _type, _value, tb):
        if tb is None:
            self.commit()
        else:
            self.rollback()

    def __init__(self):
        self.filename = DB_PATH
        self.db = self.connect()
        self.bootstrap()

    def begin_transaction(self):
        """ begin a transaction """
        self.query('BEGIN TRANSACTION')

    def bootstrap(self):
        """ bootstrap database """
        for query in BOOTSTRAP:
            self.query(query)

    def commit(self):
        """ commit update(s) """
        self.db.commit()

    def connect(self):
        """ connect to database """
        folder = os.path.dirname(self.filename)
        if not os.path.exists(folder):
            os.makedirs(folder)

        db = sqlite.connect(self.filename)
        db.isolation_level = None
        db.text_factory = str
        return db

    def insert(self, table, props):
        """ insert task into database """
        fields = []
        marks = []
        params = []

        for k, v in props.items():
            fields.append('`' + k + '`')
            marks.append('?')
            params.append(v)

        query = f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({', '.join(marks)})"
        return self.query(query, params)

    def log_exception(self, msg):
        """ log exception """
        logger.error(msg)

    def query(self, query, params=None):
        """ query database """
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
            if query.startswith('INSERT '):
                return cur.lastrowid
            return cur.rowcount
        except:
            self.log_exception(f'failed SQL statement: {query}, params: {params}')
            raise
        finally:
            cur.close()

    def rollback(self):
        """ rollback changes """
        self.db.rollback()

    def update(self, table, props, conditions):
        """ update task """
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

        query = f"UPDATE {table} SET {', '.join(parts)}"
        if where:
            query += f" WHERE {' AND '.join(where)}"

        return self.query(query, params)

class Database(DAL):
    """ Database methods """

    def add_task(self, command):
        """ add task """
        if not isinstance(command, (list, tuple)):
            logger.error('task command must be list of arguments')
            raise ValueError('task command must be list of arguments')

        cmd_str = ' '.join(str(x) for x in command)
        logger.debug(f"add_task - command: {command}, cmd_str: {cmd_str}")

        return self.insert('tasks', {
            'added_at': int(time.time()),
            'command': cmd_str,
            'status': 0,
        })

    def get_next_task(self):
        """ get next task """
        rows = self.query('SELECT id, command FROM tasks WHERE status = 0 ORDER BY id LIMIT 1')
        return rows[0] if rows else None

    def get_task(self, task_id):
        """ get task details """
        rows = self.query('SELECT * FROM tasks WHERE id = ?', [task_id])
        return rows[0] if rows else None

    def list_failed_tasks(self):
        """ list failed tasks """
        rows = self.query('SELECT id, run_at, added_at, finished_at, command, status,\
            result FROM tasks WHERE status = 2 AND result <> 0 ORDER BY id')
        return rows, len(rows)

    def list_finished_tasks(self):
        """ list finished tasks """
        rows = self.query('SELECT id, run_at, added_at, finished_at, command, status,\
            result FROM tasks WHERE status = 2 AND result = 0 ORDER BY id')
        return rows, len(rows)

    def list_last_tasks(self):
        """ list last tasks """
        rows = self.query('SELECT id, run_at, added_at, finished_at, command, status,\
            result FROM tasks ORDER BY id DESC LIMIT 50')
        return reversed(rows), len(rows)

    def list_pending_tasks(self):
        """ list pending tasks """
        rows = self.query('SELECT id, run_at, added_at, finished_at, command, status,\
            result FROM tasks WHERE status = 0 ORDER BY id')
        return rows, len(rows)

    def purge_older(self):
        """ Delete tasks older than 1 week. """
        since = time.time() - 86400 * 7
        count = self.query('DELETE FROM tasks WHERE added_at < ?', [since])
        return count

    def purge_pending(self):
        """ Delete all pending tasks """
        return self.query('DELETE FROM tasks WHERE status = 0')

    def replace_task(self, command):
        """ replace task """
        if not isinstance(command, (list, tuple)):
            logger.error('task command must be list of arguments')
            raise ValueError('task command must be list of arguments')

        cmd_str = ' '.join(str(x) for x in command)
        logger.debug(f"replace_task - command: {command}, cmd_str: {cmd_str}")

        self.query('DELETE FROM tasks WHERE command = ?', [cmd_str])
        return self.add_task(command)

    def reset_running(self):
        """ reset running tasks """
        self.query('UPDATE tasks SET status = 0 WHERE status = 1')

        Email.send_mail("Running Tasks reset",\
                    "All running tasks were reset, please check them and re-run as necessary")

    def set_failed(self, task_id, command, msg, ctime):
        """ set status to failed """
        logger.debug(f"set_failed: [{task_id}], [{command}], [{msg}], [{ctime}]")

        if not isinstance(task_id, int):
            logger.error('task_id must be an integer')
            raise ValueError('task_id must be an integer')

        Email.send_mail("Task Failed", f"Task id: {task_id}\nTask: {command}\nOutput: {msg}")

        return self.update('tasks', {
            'status': 2,
            'stderr': msg,
            'result': -1,
            'finished_at': int(time.time()),
            'time_r': ctime.rtime,
            'time_u': ctime.utime,
            'time_s': ctime.stime,
        }, {
            'id': task_id,
        })

    def set_finished(self, task_id, command, coutput, ctime):
        """ set status to finished """
        logger.debug(f"set_finished: [{task_id}], [{command}], [{coutput}], [{ctime}]")

        if not isinstance(task_id, int):
            logger.error('task_id must be an integer')
            raise ValueError('task_id must be an integer')

        if not command == 'reload':
            Email.send_mail("Task Finished", f"Task id: {task_id}\nTask: {command}\n\
                            Output: {coutput.stdout}\nError: {coutput.stderr}")

        return self.update('tasks', {
            'status': 2,
            'stdout': coutput.stdout if coutput and coutput.stdout else None,
            'stderr': coutput.stderr if coutput and coutput.stderr else None,
            'result': coutput.rc,
            'finished_at': int(time.time()),
            'time_r': ctime.rtime,
            'time_u': ctime.utime,
            'time_s': ctime.stime,
        }, {
            'id': task_id,
        })

    def set_running(self, task_id):
        """ set status to running """
        logger.debug(f"set_running: [{task_id}]")

        if not isinstance(task_id, int):
            logger.error('task_id must be an integer')
            raise ValueError('task_id must be an integer')

        return self.update('tasks', {
            'status': 1,
            'run_at': int(time.time()),
        }, {
            'id': task_id,
        })
