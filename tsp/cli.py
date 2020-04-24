# vim: set ts=4 sts=4 sw=4 et tw=0 fileencoding=utf-8:

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


def calc_times(then):
    now = os.times()

    utime = now[0] - then[0]
    stime = now[1] - then[1]
    rtime = now[4] - then[4]

    return rtime, utime, stime

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

    print_task_list(tasks, 'Failed tasks:', 'No failed tasks.')


def do_list_finished():
    with Database() as db:
        tasks = db.list_finished_tasks()

    print_task_list(tasks, 'Finished tasks:', 'No finished tasks.')


def do_list_last():
    with Database() as db:
        tasks = db.list_last_tasks()

    print_task_list(tasks, 'Recent tasks:', 'No recent tasks.')


def do_list_pending():
    with Database() as db:
        tasks = db.list_pending_tasks()

    print_task_list(tasks, 'Pending tasks:', 'No pending tasks.')


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

        times = os.times()

        db.set_running(int(task['id']))
        db.commit()

        try:
            rc, out, err = run_command(task['command'])
            rtime, utime, stime = calc_times(times)
            db.set_finished(int(task['id']), rc, out, err, rtime, utime, stime)
        except Exception, e:
            rtime, utime, stime = calc_times(times)
            db.set_failed(int(task['id']), str(e), rtime, utime, stime)
            print('Task %d failed.' % int(task['id']))

        db.commit()


def do_show(task_id):
    with Database() as db:
        task = db.get_task(int(task_id))

    date_fmt = '%Y-%m-%d %H:%M:%S'

    print('task id    : %d' % task['id'])
    print('added at   : %s' % time.strftime(date_fmt, time.localtime(task['added_at'])))

    if task['run_at']:
        print('run at     : %s' % time.strftime(date_fmt, time.localtime(task['run_at'])))
    else:
        print('run at     : never')

    if task['finished_at']:
        print('finished at: %s' % time.strftime(date_fmt, time.localtime(task['finished_at'])))
    else:
        print('finished at: never')

    print('command    : %s' % task['command'])

    print('result     : %d' % task['result'])

    if task['time_r']:
        print('real time  : %.2f' % task['time_r'])
    if task['time_u']:
        print('user time  : %.2f' % task['time_u'])
    if task['time_s']:
        print('sys time   : %.2f' % task['time_s'])

    if not task['stdout']:
        print('stdout     : empty')

    if not task['stderr']:
        print('stderr     : empty')

    if task['stdout']:
        print("\n--- stdout ---\n\n%s\n" % task['stdout'].encode('utf-8').rstrip())

    if task['stderr']:
        print("\n--- stderr ---\n\n%s\n" % task['stderr'].encode('utf-8').rstrip())


def main():
    action = None
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
        elif arg == '--show':
            action = 'show'
        elif arg.startswith('--'):
            return do_help()
        else:
            command = sys.argv[idx+1:]
            if action is None:
                action = 'add'
            break

    if action == 'add':
        do_add(replace, command)
    elif action == 'show':
        do_show(command[0])
    else:
        do_list_last()


def print_task_list(tasks, header, no_header):
    if not tasks:
        print(no_header)

    else:
        print('--- %s ---' % header)
        print('   id  date   time   dur  res command')
        print('----- ------ ------ ---- ---- -----------------')
        for t in tasks:
            ts = time.strftime('%d.%m  %H:%M', time.localtime(t['finished_at']))

            if t['status'] == 0:
                mark = '-'
            elif t['status'] == 1:
                mark = '*'
            elif t['result'] == 0:
                mark = u'✓'
            else:
                mark = 'x'

            if t['finished_at']:
                dur = t['finished_at'] - t['run_at']
            else:
                dur = 0

            print('%5d  %s  %3u  %s   %s' % (t['id'], ts, dur, mark, t['command']))


def run_command(command):
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    return p.returncode, out, err
