from __future__ import print_function

import sys

from database import Database


def do_add(replace, command):
    if command is None:
        print('Command not specified.', file=sys.stderr)
        exit(1)

    with Database() as db:
        task_id = db.add_task(command)

    print('Task %d added.' % task_id)


def do_help():
    print('Usage: tsp [-r] [command with arguments]', file=sys.stderr)
    exit(1)


def do_list():
    with Database() as db:
        tasks = db.list_pending_tasks()

    if not tasks:
        print('No pending tasks.')

    else:
        for t in tasks:
            print('%d %s' % (t[0], t[1]))


def main():
    action = 'list'
    replace = False
    command = None

    for idx, arg in enumerate(sys.argv[1:]):
        if arg == '-r':
            replace = True
            continue
        else:
            command = sys.argv[idx+1:]
            action = 'add'

    if action == 'list':
        do_list()
    elif action == 'add':
        do_add(replace, command)
    else:
        do_help()
