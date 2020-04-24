# vim: set ts=4 sts=4 sw=4 et tw=0:

from __future__ import print_function

import errno
import fcntl
import os
import subprocess
import sys
import time

from database import Database


USAGE = """Task spooler.  Serializes background process execution.

Usage:

tsp command            -- add task to the queue.
tsp --replace command  -- add to the queue, removing existing unfinished entries.
tsp --pending          -- list pending tasks.
tsp --finished         -- list finished tasks.
tsp --failed           -- list failed tasks.
tsp --purge            -- delete pending tasks.
tsp --run              -- run the daemon.
"""


def do_add(replace, command):
    if command is None:
        print('Command not specified.', file=sys.stderr)
        exit(1)

    with Database() as db:
        task_id = db.add_task(command)

    print('Task %d added.' % task_id)


def do_help():
    print(USAGE, file=sys.stderr)
    exit(1)


def do_list_failed():
    with Database() as db:
        tasks = db.list_failed_tasks()

    if not tasks:
        print('No failed tasks.')

    else:
        for t in tasks:
            print('%d %s' % (t[0], t[1]))


def do_list_finished():
    with Database() as db:
        tasks = db.list_finished_tasks()

    if not tasks:
        print('No finished tasks.')

    else:
        for t in tasks:
            print('%d %s' % (t[0], t[1]))


def do_list_pending():
    with Database() as db:
        tasks = db.list_pending_tasks()

    if not tasks:
        print('No pending tasks.')

    else:
        for t in tasks:
            print('%d %s' % (t[0], t[1]))


def do_purge():
    with Database() as db:
        count = db.purge_pending()
        print('Deleted %d unfinished tasks.' % count)


def do_run():
    try:
        lock = os.path.expanduser('~/.cache/tsp.lock')
        flock = open(lock, 'w')
        fcntl.lockf(flock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError, e:
        if e.errno == errno.EAGAIN:
            print('tsp daemon is already running', file=sys.stderr)
            exit(1)
        else:
            raise

    db = Database()

    db.reset_running()
    db.commit()

    while True:
        task = db.get_next_task()

        if task is None:
            db.commit()
            time.sleep(1)
            continue

        print('Running task %d: %s' % (int(task['id']), task['command']))

        db.set_running(int(task['id']))
        db.commit()

        try:
            rc, out, err = run_command(task['command'])
            db.set_finished(int(task['id']), rc, out, err)
        except Exception, e:
            db.set_failed(int(task['id']), str(e))
            print('Task %d failed.' % int(task['id']))

        db.commit()


def main():
    action = 'help'
    replace = False
    command = None

    for idx, arg in enumerate(sys.argv[1:]):
        if arg == '--failed':
            return do_list_failed()
        elif arg == '--finished':
            return do_list_finished()
        elif arg == '--pending':
            return do_list_pending()
        elif arg == '--pending':
            return do_list_pending()
        elif arg == '--purge':
            return do_purge()
        elif arg == '--replace':
            replace = True
            continue
        elif arg == '--run':
            return do_run()
        elif arg.startswith('--'):
            return do_help()
        else:
            command = sys.argv[idx+1:]
            action = 'add'

    if action == 'add':
        do_add(replace, command)
    else:
        do_help()


def run_command(command):
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    return p.returncode, out, err
