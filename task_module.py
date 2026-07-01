# -*- coding: utf-8 -*-
"""启元智脑 · 跨对话任务管理模块"""
import io, os, json, uuid
from datetime import datetime, timedelta

BRAIN_DIR = os.path.dirname(os.path.abspath(__file__))
TASKS_FILE = os.path.join(BRAIN_DIR, 'tasks.json')
RECURRING_FILE = os.path.join(BRAIN_DIR, 'recurring.json')

def _load_tasks():
    if not os.path.exists(TASKS_FILE):
        return {'tasks': [], '_meta': {'version': '1.0', 'total_completed': 0}}
    with io.open(TASKS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def _save_tasks(data):
    with io.open(TASKS_FILE, 'w', encoding='utf-8', newline='') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def cmd_task_add(args):
    data = _load_tasks()
    task = {
        'id': str(uuid.uuid4())[:8],
        'title': args.title,
        'priority': args.priority or 'P2',
        'status': 'pending',
        'created': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'done_at': None,
        'source': 'cli'
    }
    data['tasks'].append(task)
    _save_tasks(data)
    print('[OK] ' + task['id'] + ' | ' + task['title'] + ' | ' + task['priority'])

def cmd_task_list(args):
    data = _load_tasks()
    tasks = data['tasks']
    if not args.all:
        tasks = [t for t in tasks if t['status'] == 'pending']
    if args.priority:
        tasks = [t for t in tasks if t['priority'] == args.priority]
    if not tasks:
        print('[OK] no pending tasks')
        return
    print('=' * 50)
    print('  Tasks: ' + str(len(tasks)))
    print('=' * 50)
    for t in sorted(tasks, key=lambda x: ({'P0':0,'P1':1,'P2':2}.get(x['priority'],3), x['created'])):
        icon = '[ ]' if t['status'] == 'pending' else '[X]'
        line = '  ' + icon + ' [' + t['priority'] + '] ' + t['id'] + ' | ' + t['title'] + ' | ' + t['created']
        print(line)

def cmd_task_done(args):
    data = _load_tasks()
    for t in data['tasks']:
        if t['id'] == args.task_id:
            t['status'] = 'done'
            t['done_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
            data['_meta']['total_completed'] = data['_meta'].get('total_completed', 0) + 1
            _save_tasks(data)
            print('[OK] Done: [' + t['id'] + '] ' + t['title'])
            return
    print('[ERR] Not found: ' + args.task_id)

def cmd_task_recurring(args):
    with io.open(RECURRING_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    now = datetime.now()
    print('=' * 50)
    print('  Recurring: ' + str(len(data['tasks'])))
    print('=' * 50)
    days = {'Monday':0,'Tuesday':1,'Wednesday':2,'Thursday':3,'Friday':4,'Saturday':5,'Sunday':6}
    for t in data['tasks']:
        freq = t['frequency']
        if freq == 'daily':
            due = True
            label = now.strftime('%Y-%m-%d')
        elif freq == 'weekly':
            due = (now.weekday() == days.get(t.get('day','Monday'), 0))
            label = t.get('day','?')
        elif freq == 'monthly':
            due = (now.day == t.get('day',1))
            label = 'day ' + str(t.get('day','?'))
        else:
            due = False
            label = '?'
        icon = '[!!]' if due else '[  ]'
        print('  ' + icon + ' ' + t['id'] + ' | ' + t['title'] + ' | ' + freq + ' | ' + label)

def get_pending_tasks():
    data = _load_tasks()
    return [t for t in data['tasks'] if t['status'] == 'pending']

def get_recurring_due_today():
    with io.open(RECURRING_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    now = datetime.now()
    due = []
    days = {'Monday':0,'Tuesday':1,'Wednesday':2,'Thursday':3,'Friday':4,'Saturday':5,'Sunday':6}
    for t in data['tasks']:
        if t['frequency'] == 'daily':
            due.append(t)
        elif t['frequency'] == 'weekly':
            if now.weekday() == days.get(t.get('day','Monday'), 0):
                due.append(t)
        elif t['frequency'] == 'monthly':
            if now.day == t.get('day', 1):
                due.append(t)
    return due