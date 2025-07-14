# vim: set ts=4 sts=4 sw=4 et tw=0 fileencoding=utf-8:
""" CLI implementation """

import errno
import fcntl
import os
import subprocess
import sys
import time

from dataclasses import dataclass
import sqlite3
from tsp.database import Database

USAGE = """Task spooler.  Serializes background process execution.

Usage:

tsp command            -- add task to the queue.
tsp --replace command  -- add to the queue, removing existing unfinished entries.
tsp --show             -- list all tasks
tsp --pending          -- list pending tasks.
tsp --finished         -- list finished tasks.
tsp --failed           -- list failed tasks.
tsp --purge            -- delete pending tasks.
tsp --run              -- run the daemon.
"""

@dataclass
class CalcTimes:
    """ Calculated Times """
    @staticmethod
    def get_none():
        """ used for no-op """
        return None, None, None

    @staticmethod
    def get_elapsed(then):
        """ get elapsed times """
        now = os.times()
        utime = now[0] - then[0]
        stime = now[1] - then[1]
        rtime = now[4] - then[4]
        return utime, stime, rtime

@dataclass
class CmdOutput:
    """ Command return values """
    @staticmethod
    def get_result(returncode, output, error):
        """ return params """
        return returncode, output, error


def do_add(_replace, command):
    """ Add command to database """
    if command is None:
        print('Command not specified.', file=sys.stderr)
        sys.exit(1)

    with Database() as db:
        task_id = db.add_task(command)

    print(f'Task {task_id} added.')


def do_help():
    """ Show usage """
    print(USAGE, file=sys.stderr)
    sys.exit(1)


def do_list_failed():
    """ list failed commands """
    with Database() as db:
        tasks = db.list_failed_tasks()

    print_task_list(tasks, 'Failed tasks:', 'No failed tasks.')


def do_list_finished():
    """ list finished commands """
    with Database() as db:
        tasks = db.list_finished_tasks()

    print_task_list(tasks, 'Finished tasks:', 'No finished tasks.')


def do_list_last():
    """ list last command """
    with Database() as db:
        tasks = db.list_last_tasks()

    print_task_list(tasks, 'Recent tasks:', 'No recent tasks.')


def do_list_pending():
    """ list pending command(s) """
    with Database() as db:
        tasks = db.list_pending_tasks()

    print_task_list(tasks, 'Pending tasks:', 'No pending tasks.')


def do_purge():
    """ purge remaing commands """
    with Database() as db:
        count = db.purge_pending()
        print(f'Deleted {count} unfinished tasks.')


def do_run():
    """ run scheduler precoess """
    try:
        lock = os.path.expanduser('~/.cache/tsp.lock')
        with open(lock, 'w', encoding="utf-8") as flock:
            fcntl.lockf(flock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError as e:
        if e.errno == errno.EAGAIN:
            print('tsp daemon is already running', file=sys.stderr)
            sys.exit(1)
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

        print(f"Running task {int(task['id'])}: {task['command']}")

        if task['command'] == 'reload':
            db.set_finished(int(task['id']), CmdOutput.get_result(0, None, None),\
                            CalcTimes.get_none())
            db.commit()
            print('Reloading.')
            sys.exit(0)

        times = os.times()

        db.set_running(int(task['id']))
        db.commit()

        try:
            db.set_finished(int(task['id']), run_command(task['command']),\
                            CalcTimes.get_elapsed(times))
            print(f"Task {int(task['id'])} finished.")
        except (ValueError, sqlite3.Error) as e:
            db.set_failed(int(task['id']), str(e), CalcTimes.get_elapsed(times))
            print(f"Task {int(task['id'])} failed: {e}.")

        db.commit()


def do_show(task_id):
    """ show commands """
    with Database() as db:
        task = db.get_task(int(task_id))

    date_fmt = '%Y-%m-%d %H:%M:%S'

    print(f"task id    : {task['id']}")
    print(f"added at   : {time.strftime(date_fmt, time.localtime(task['added_at']))}")

    print(f"run at     : {time.strftime(date_fmt, time.localtime(task['run_at']))}"
        if task['run_at'] else 'run at     : never')

    print(f"finished at: {time.strftime(date_fmt, time.localtime(task['finished_at']))}"
        if task['finished_at'] else 'finished at: never')

    print(f"command    : {task['command']}")

    print(f"result     : {task['result']}"
        if task['result'] is not None else 'result     : none')

    if task['time_r']:
        print(f"real time  : {task['time_r']}")
    if task['time_u']:
        print(f"user time  : {task['time_u']}")
    if task['time_s']:
        print(f"sys time   : {task['time_s']}")

    if not task['stdout']:
        print('stdout     : empty')

    if not task['stderr']:
        print('stderr     : empty')

    if task['stdout']:
        print(f"\n--- stdout ---\n\n{str(task['stdout']).rstrip()}\n")

    if task['stderr']:
        print(f"\n--- stderr ---\n\n{str(task['stderr']).rstrip()}\n")


def find_executable(command):
    """ find command executeable """
    if os.path.exists(command):
        return command

    base = os.path.basename(command)

    for folder in os.getenv('PATH').split(os.path.pathsep):
        exe = os.path.join(folder, base)
        if os.path.exists(exe):
            return exe

    raise RuntimeError(f'command {base} not found')


def main():
    """ process command line arguments """
    replace = False

    if len(sys.argv) - 1 == 0:
        return do_list_last()
    for idx, arg in enumerate(sys.argv[1:]):
        if arg == '--replace':
            replace = True
            continue
        if not arg.startswith('--'):
            return do_add(replace, arg.split())
        if arg == "--show":
            if len(sys.argv) -1 == 2:
                task_id = sys.argv[idx+1:]
                return do_show(task_id)
            print("Missing Task ID")
            continue
        # handle other options
        return {
            '--pending': do_list_pending(),
            '--finished': do_list_finished(),
            '--failed': do_list_failed(),
            '--purge': do_purge(),
            '--run': do_run(),
            '--*': do_help(),
        }.get(arg)


def print_task_list(tasks, header, no_header):
    """ print tasks list """

    print(f"print_task_list - Tasks: [{tasks}]\n\n[{header}]\n\n[{no_header}]")

    if not tasks:
        print(no_header)

    else:
        print(f'--- {header} ---')
        print('   id  date   time   dur  res command')
        print('----- ------ ------ ---- ---- -----------------')
        for t in tasks:
            ts = time.strftime('%d.%m  %H:%M', time.localtime(t['finished_at']))

            if t['status'] == 0:
                mark = '-'
            elif t['status'] == 1:
                mark = '*'
            elif t['result'] == 0:
                mark = '✓'
            else:
                mark = 'x'

            if t['finished_at'] and t['run_at']:
                dur = t['finished_at'] - t['run_at']
            else:
                dur = 0

            print(f"{t['id']}  {ts}  {dur}  {mark}   {t['command']}")


def run_command(command):
    """ run command """
    command = command.split()
    command[0] = find_executable(command[0])
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as p:
        return CmdOutput.get_result(p.returncode, *(p.communicate()))
