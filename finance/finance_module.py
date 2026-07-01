# -*- coding: utf-8 -*-
# P0-6/7/8: Finance module - token estimation, project cost, financial reports.
# Pricing: DeepSeek V4 Pro - input $0.5/M, output $2/M tokens

import os, io, json, sqlite3
from datetime import datetime, timedelta
from collections import defaultdict

# Token estimation per operation type (input, output)
_OP_TOKENS = {
    'rule_check': (500, 200),
    'kb_search': (800, 300),
    'evolve': (2000, 1000),
    'chat': (1000, 500),
    'audit': (300, 100),
    'health': (400, 200),
    'probe': (600, 300),
    'safe_write': (200, 100),
    'hr': (400, 200),
    'cost': (200, 100),
}

_PRICE_INPUT = 0.50   # per 1M tokens
_PRICE_OUTPUT = 2.00  # per 1M tokens

def _detect_op_type(action, target_path='', details=''):
    action_lower = (action or '').lower()
    if 'rule' in action_lower: return 'rule_check'
    if 'kb' in action_lower or 'search' in action_lower: return 'kb_search'
    if 'evolve' in action_lower: return 'evolve'
    if 'chat' in action_lower: return 'chat'
    if 'audit' in action_lower: return 'audit'
    if 'health' in action_lower: return 'health'
    if 'probe' in action_lower: return 'probe'
    if 'safe' in action_lower or 'write' in action_lower: return 'safe_write'
    if 'hr' in action_lower: return 'hr'
    if 'cost' in action_lower: return 'cost'
    return 'chat'

class FinanceModule:
    def __init__(self, brain_dir=None):
        if brain_dir is None:
            brain_dir = os.path.dirname(os.path.abspath(__file__))
            if 'finance' in os.path.basename(brain_dir):
                brain_dir = os.path.dirname(brain_dir)
        self.brain_dir = brain_dir
        self.finance_dir = os.path.join(brain_dir, 'finance')
        os.makedirs(self.finance_dir, exist_ok=True)
        self.audit_db = os.path.join(brain_dir, 'audit', 'audit.db')
        self.cost_db = os.path.join(self.finance_dir, 'cost.db')
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.cost_db)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS cost_estimates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                op_type TEXT,
                count INTEGER DEFAULT 0,
                est_input_tokens REAL DEFAULT 0,
                est_output_tokens REAL DEFAULT 0,
                est_cost_usd REAL DEFAULT 0,
                project TEXT DEFAULT 'general'
            );
            CREATE TABLE IF NOT EXISTS cost_daily (
                date TEXT PRIMARY KEY,
                total_ops INTEGER DEFAULT 0,
                total_input_tokens REAL DEFAULT 0,
                total_output_tokens REAL DEFAULT 0,
                total_cost_usd REAL DEFAULT 0,
                total_cost_cny REAL DEFAULT 0
            );
        ''')
        conn.commit()
        conn.close()

    def _load_audit_logs(self, since_days=90):
        if not os.path.isfile(self.audit_db):
            return []
        conn = sqlite3.connect(self.audit_db)
        conn.row_factory = sqlite3.Row
        since = (datetime.now() - timedelta(days=since_days)).strftime('%Y-%m-%d')
        try:
            rows = conn.execute(
                'SELECT * FROM audit_logs WHERE timestamp >= ? ORDER BY timestamp ASC',
                (since,)
            ).fetchall()
        except Exception:
            rows = []
        conn.close()
        return [dict(r) for r in rows]

    def estimate(self, since_days=90):
        logs = self._load_audit_logs(since_days)
        if not logs:
            return {'ok': True, 'message': 'No audit data', 'estimates': []}

        by_date_type = defaultdict(lambda: defaultdict(int))
        for log in logs:
            date = (log.get('timestamp', '') or '')[:10]
            action = log.get('action', '') or ''
            op_type = _detect_op_type(action)
            by_date_type[date][op_type] += 1

        estimates = []
        total_usd = 0.0
        for date in sorted(by_date_type.keys()):
            day_ops = 0
            day_input = 0.0
            day_output = 0.0
            for op_type, count in sorted(by_date_type[date].items()):
                itok, otok = _OP_TOKENS.get(op_type, (500, 300))
                est_input = count * itok / 1_000_000
                est_output = count * otok / 1_000_000
                cost = est_input * _PRICE_INPUT + est_output * _PRICE_OUTPUT
                day_ops += count
                day_input += est_input
                day_output += est_output
                estimates.append({
                    'date': date, 'op_type': op_type, 'count': count,
                    'est_input_tokens_m': round(est_input, 4),
                    'est_output_tokens_m': round(est_output, 4),
                    'est_cost_usd': round(cost, 6),
                })
                total_usd += cost

        # Daily aggregation
        by_date = defaultdict(lambda: {'ops': 0, 'input': 0.0, 'output': 0.0, 'cost': 0.0})
        for e in estimates:
            d = e['date']
            by_date[d]['ops'] += e['count']
            by_date[d]['input'] += e['est_input_tokens_m']
            by_date[d]['output'] += e['est_output_tokens_m']
            by_date[d]['cost'] += e['est_cost_usd']

        daily = [{'date': d, **v} for d, v in sorted(by_date.items())]

        # Save to DB
        conn = sqlite3.connect(self.cost_db)
        for d in daily:
            conn.execute(
                'INSERT OR REPLACE INTO cost_daily (date, total_ops, total_input_tokens, total_output_tokens, total_cost_usd, total_cost_cny) VALUES (?,?,?,?,?,?)',
                (d['date'], d['ops'], round(d['input'], 4), round(d['output'], 4), round(d['cost'], 6), round(d['cost'] * 7.25, 2))
            )
        conn.commit()
        conn.close()

        return {
            'ok': True,
            'period_days': since_days,
            'total_ops': sum(d['ops'] for d in daily),
            'total_cost_usd': round(total_usd, 4),
            'total_cost_cny': round(total_usd * 7.25, 2),
            'daily': daily,
            'by_type': estimates,
        }

    def by_project(self):
        logs = self._load_audit_logs(90)
        proj_costs = defaultdict(lambda: {'ops': 0, 'cost': 0.0})
        for log in logs:
            target = log.get('target_path', '') or ''
            if '04_项目' in target:
                proj = 'projects'
            elif 'brain' in target:
                proj = 'brain_dev'
            elif '01_公司' in target:
                proj = 'governance'
            else:
                proj = 'general'
            action = log.get('action', '') or ''
            op_type = _detect_op_type(action)
            itok, otok = _OP_TOKENS.get(op_type, (500, 300))
            cost = (itok * _PRICE_INPUT + otok * _PRICE_OUTPUT) / 1_000_000
            proj_costs[proj]['ops'] += 1
            proj_costs[proj]['cost'] += cost

        return {
            'ok': True,
            'projects': {k: {'ops': v['ops'], 'cost_usd': round(v['cost'], 4), 'cost_cny': round(v['cost'] * 7.25, 2)}
                         for k, v in sorted(proj_costs.items())}
        }

    def report(self):
        est = self.estimate(90)
        proj = self.by_project()
        daily = est.get('daily', [])
        weekly_cost = 0.0
        monthly_cost = 0.0
        now = datetime.now()
        for d in daily:
            dd = datetime.strptime(d['date'], '%Y-%m-%d')
            if (now - dd).days <= 7:
                weekly_cost += d['cost']
            if (now - dd).days <= 30:
                monthly_cost += d['cost']

        return {
            'ok': True,
            'period': '90 days',
            'pricing': 'DeepSeek V4 Pro: input $0.5/M, output $2/M',
            'total_estimated_cost_usd': est.get('total_cost_usd', 0),
            'total_estimated_cost_cny': est.get('total_cost_cny', 0),
            'weekly_cost_usd': round(weekly_cost, 4),
            'monthly_cost_usd': round(monthly_cost, 4),
            'weekly_cost_cny': round(weekly_cost * 7.25, 2),
            'monthly_cost_cny': round(monthly_cost * 7.25, 2),
            'total_ops': est.get('total_ops', 0),
            'by_project': proj.get('projects', {}),
            '_note': 'estimated based on audit log counts - actual API costs may differ',
        }