# pylint: disable=logging-fstring-interpolation, too-many-return-statements
# vim: set ts=4 sts=4 sw=4 et tw=0 fileencoding=utf-8:
""" CLI implementation """

import logging
import errno
import fcntl
import os
import subprocess
import sys
import time
import sqlite3

from optparse import OptionParser
from dataclasses import dataclass
from tsp.database import Database

logger = logging.getLogger(__name__)

@dataclass
class CalcTimes:
    """ Calculated Times """
    utime = None
    stime = None
    rtime = None
    def get_elapsed(self, then):
        """ get elapsed times """
        now = os.times()
        self.utime = now[0] - then[0]
        self.stime = now[1] - then[1]
        self.rtime = now[4] - then[4]
        return self


@dataclass
class CmdOutput:
    """ Command return values """
    rc = 0
    stdout = None
    stderr = None
    def get_result(self, returncode, output, error):
        """ use passed params """
        self.rc = returncode
        self.stdout = output
        self.stderr = error
        return self


def do_add(replace, command):
    """ Add command to database """
    if command is None:
        logger.error('Command not specified.')
        sys.exit(1)

    with Database() as db:
        if replace:
            task_id = db.replace_task(command)
        else:
            task_id = db.add_task(command)

    logger.info(f'Task {task_id} added.')


def do_list_failed():
    """ list failed commands """
    with Database() as db:
        tasks, count = db.list_failed_tasks()

    print_task_list(tasks, count, 'Failed tasks:', 'No failed tasks.')


def do_list_finished():
    """ list finished commands """
    with Database() as db:
        tasks, count = db.list_finished_tasks()

    print_task_list(tasks, count, 'Finished tasks:', 'No finished tasks.')


def do_list_last():
    """ list last command """
    with Database() as db:
        tasks, count = db.list_last_tasks()

    print_task_list(tasks, count, 'Recent tasks:', 'No recent tasks.')


def do_list_pending():
    """ list pending command(s) """
    with Database() as db:
        tasks, count = db.list_pending_tasks()

    print_task_list(tasks, count, 'Pending tasks:', 'No pending tasks.')


def do_purge():
    """ purge remaining commands """
    with Database() as db:
        count = db.purge_pending()
        logger.info(f'Deleted {count} unfinished tasks.')


def do_run():
    """
        Runs scheduler process

        This should normally be done from a systemd unit

    """
    try:
        lock = os.path.expanduser('~/.cache/tsp.lock')
        with open(lock, 'w', encoding="utf-8") as flock:
            fcntl.lockf(flock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError as e:
        if e.errno == errno.EAGAIN:
            logger.error('tsp daemon is already running', file=sys.stderr)
            sys.exit(1)
        else:
            raise

    db = Database()

    db.reset_running()
    db.commit()

    db.purge_older()
    db.commit()

    while True:
        task = db.get_next_task()

        if task is None:
            db.commit()
            time.sleep(1)
            continue

        logger.info(f"Running task {int(task['id'])}: {task['command']}")

        cout = CmdOutput()
        ctim = CalcTimes()

        if task['command'] == 'reload':
            db.set_finished(int(task['id']), task['command'],
                            cout.get_result(0, None, None), ctim.get_elapsed(os.times()))
            db.commit()
            logger.info('Reloading Tasks.')
            sys.exit(0)

        db.set_running(int(task['id']))
        db.commit()

        try:
            output = run_command(task['command'])
            logger.debug(f"do_run: command: {task['command']}, output: {output}")
            db.set_finished(int(task['id']), task['command'], output, ctim.get_elapsed(os.times()))
            logger.info(f"Task {int(task['id'])} finished.")
        except (ValueError, sqlite3.Error) as e:
            db.set_failed(int(task['id']), task['command'], str(e), ctim.get_elapsed(os.times()))
            logger.error(f"Task {int(task['id'])} failed: {e}.")

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

    logger.error(f'command {base} not found')
    raise RuntimeError(f'command {base} not found')


def main():
    """ process command line arguments """

    parser = OptionParser()
    parser.set_defaults(verbose=True)
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose",
                      help="print status messages to stdout")
    parser.add_option("-q", "--quiet",
                      action="store_false", dest="verbose",
                      help="don't print status messages to stdout")
    # parser.add_option("-a", "--add",
    #                   dest="task",
    #                   help="add a task to the queue")
    parser.add_option("--replace",
                      action="store_true", dest="replace",
                      help="replace a task in the queue")
    parser.add_option("-s", "--show",
                      action="store", type="int",
                      dest="task_id",
                      help="list task entry")
    parser.add_option("-p", "--pending",
                      action='store_true',
                      help="list pending tasks")
    parser.add_option("-e", "--finished",
                      action='store_true',
                      help="list finished tasks")
    parser.add_option("-f", "--failed",
                      action='store_true',
                      help="list failed tasks")
    parser.add_option("-d", "--purge",
                      action='store_true',
                      help="delete pending tasks")
    parser.add_option("--run",
                      action='store_true',
                      help="run the daemon")

    (opts, args) = parser.parse_args()
    if opts.verbose:
        logger.setLevel("DEBUG")

    logger.debug(f"Options: {opts}, Args: {args}")

    if opts.pending:
        return do_list_pending()
    if opts.finished:
        return do_list_finished()
    if opts.failed:
        return do_list_failed()
    if opts.purge:
        return do_purge()
    if opts.run:
        return do_run()
    if opts.task_id:
        return do_show(opts.task_id)

    # add a task
    if len(args) > 0:
        return do_add(opts.replace, args)

    return do_list_last()


def print_task_list(tasks, count, header, no_header):
    """ print tasks list """

    logger.debug(f"print_task_list - Tasks: [{tasks}]\n[{count}]\n[{header}]\n[{no_header}]")

    if count == 0:
        print(no_header)

    else:
        print(f'--- {header} ---')
        # print('   id  date   time   dur  res command')
        # print('----- ------ ------ ---- ---- -----------------')
        # for t in tasks:
            # ts = time.strftime('%d.%m  %H:%M', time.localtime(t['finished_at']))
            # if t['status'] == 0:
            #     mark = '-'
            # elif t['status'] == 1:
            #     mark = '*'
            # elif t['result'] == 0:
            #     mark = '✓'
            # else:
            #     mark = 'x'
            # if t['finished_at'] and t['run_at']:
            #     dur = t['finished_at'] - t['run_at']
            # else:
            #     dur = 0.0

            # print(f"    {t['id']}  {ts}  {dur}    {mark} {t['command']}")

        # Original output from tsn
        # ID   State      Output               E-Level  Times(r/u/s)   Command [run=0/4]
        print('ID   State      E-Level  Times(r/u/s)   Command')

        for t in tasks:
            logger.debug(f"Task entry: {t}")
            if t['status'] == 0:
                state = 'pending'
            elif t['status'] == 1:
                state = 'running'
            elif t['status'] == 2:
                state = 'finished'
            else:
                state = 'failed'

            print(f"{t['id']}\
                {state}\
                {t['result']}\
                {t['time_r']/t['time_u']/t['time_s']}\
                {t['command']}"\
            )


def run_command(command):
    """ run command """
    command = command.split()
    command[0] = find_executable(command[0])
    logger.debug(f"run_command - command: {command}")
    cout = CmdOutput()
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as p:
        return cout.get_result(p.returncode, *(p.communicate()))
