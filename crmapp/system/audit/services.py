# audit/services.py
"""
Unified audit service.

Reads from THREE sources and merges them into one stream:
  1. AuditLog          — new unified log table (going forward)
  2. LoginLog          — existing login/logout/failed attempts
  3. UserActivityLog   — existing user management actions
"""
from itertools import chain
from django.utils import timezone
from django.db.models import Q, Count

from .models import AuditLog

# ─────────────────────────────────────────────────────────────
# WRITE
# ─────────────────────────────────────────────────────────────

def log_event(
    user, action: str, module: str, entity: str,
    before_data=None, after_data=None, severity: str = 'low',
    ip_address=None, city='', device_info='',
) -> AuditLog:
    """
    Central log creation. Always call this — never AuditLog.objects.create().
    Silently ignores errors so a logging failure never breaks a real request.
    """
    try:
        log = AuditLog(
            user=user,
            action=action,
            module=module,
            entity=entity,
            before_data=before_data,
            after_data=after_data,
            severity=severity,
            ip_address=ip_address,
            city=city or '',
            device_info=device_info or '',
        )
        log.save()
        return log
    except Exception:
        pass  # never crash the calling view


# ─────────────────────────────────────────────────────────────
# READ — unified merge across all three tables
# ─────────────────────────────────────────────────────────────

def _get_audit_qs(filters: dict = None):
    """Return filtered AuditLog queryset."""
    qs = AuditLog.objects.select_related('user', 'user__profile').order_by('-timestamp')
    if not filters:
        return qs

    if filters.get('action') and filters['action'] != 'all':
        qs = qs.filter(action=filters['action'])
    if filters.get('module') and filters['module'] != 'all':
        qs = qs.filter(module=filters['module'])
    if filters.get('severity') and filters['severity'] != 'all':
        qs = qs.filter(severity=filters['severity'])
    if filters.get('user_id'):
        qs = qs.filter(user_id=filters['user_id'])
    if filters.get('date_from'):
        qs = qs.filter(timestamp__date__gte=filters['date_from'])
    if filters.get('date_to'):
        qs = qs.filter(timestamp__date__lte=filters['date_to'])
    if filters.get('search'):
        s = filters['search']
        qs = qs.filter(
            Q(entity__icontains=s) | Q(ip_address__icontains=s)
        )
    return qs.distinct()


def _login_logs_as_dicts(filters: dict = None) -> list:
    """
    Pull LoginLog rows and normalise them into the same dict shape
    that the frontend expects.
    """
    try:
        from crmapp.system.auth_security.models import LoginLog

        STATUS_TO_ACTION = {
            'success': 'login',
            'failed':  'login_fail',
            'locked':  'login_fail',
        }

        qs = LoginLog.objects.select_related('user', 'user__profile').order_by('-timestamp')

        if filters:
            action_f = filters.get('action')
            if action_f and action_f != 'all':
                actions = action_f.split(',')
                status_list = []
                for a in actions:
                    if a == 'login': status_list.append('success')
                    elif a == 'login_fail': status_list.extend(['failed', 'locked'])
                if status_list:
                    qs = qs.filter(status__in=status_list)
                else:
                    return []

            module_f = filters.get('module')
            if module_f and module_f != 'all' and module_f != 'Auth':
                return []

            severity_f = filters.get('severity')
            if severity_f and severity_f != 'all':
                if severity_f == 'medium':
                    qs = qs.filter(status__in=['failed', 'locked'])
                elif severity_f == 'low':
                    qs = qs.filter(status='success')
                elif severity_f in ('high', 'critical'):
                    return []

            if filters.get('date_from'):
                qs = qs.filter(timestamp__date__gte=filters['date_from'])
            if filters.get('date_to'):
                qs = qs.filter(timestamp__date__lte=filters['date_to'])
            if filters.get('search'):
                s = filters['search']
                qs = qs.filter(Q(email__icontains=s) | Q(ip_address__icontains=s))

        results = []
        for row in qs:
            action   = STATUS_TO_ACTION.get(row.status, 'login_fail')
            severity = 'low' if row.status == 'success' else 'medium'

            user     = row.user
            profile  = getattr(user, 'profile', None) if user else None
            name     = profile.full_name if profile else (user.email if user else row.email_attempted)
            initials = (profile.avatar_initials if profile else
                        (name[:2].upper() if name else 'SY'))

            role = ''
            if user:
                try:
                    ur = user.user_roles.filter(is_active=True).select_related('role').first()
                    role = ur.role.name if ur else ''
                except Exception:
                    pass

            results.append({
                'id':            f'll-{row.pk}',
                'user':          user.pk if user else None,
                'user_name':     name,
                'user_initials': initials,
                'user_role':     role,
                'user_snapshot': {'name': name, 'email': row.email_attempted, 'initials': initials},
                'action':        action,
                'module':        'Auth',
                'entity':        f'{"Login" if action == "login" else "Failed Login"}: {row.email_attempted}',
                'ip_address':    getattr(row, 'ip_address', '') or '',
                'city':          getattr(row, 'city', '') or '',
                'device_info':   getattr(row, 'device_info', '') or '',
                'before_data':   None,
                'after_data':    None,
                'severity':      severity,
                'timestamp':     row.timestamp.isoformat() if row.timestamp else None,
                'ts':            row.timestamp.strftime("%Y-%m-%d %H:%M:%S") if row.timestamp else '',
            })
        return results
    except Exception:
        return []


def _activity_logs_as_dicts(filters: dict = None) -> list:
    """
    Pull UserActivityLog rows and normalise them into the same dict shape.
    """
    try:
        from crmapp.system.usermanage.models import UserActivityLog

        # (audit_action, module, severity)
        ACTION_MAP = {
            'create':   ('create',   'Users', 'medium'),
            'update':   ('update',   'Users', 'low'),
            'delete':   ('delete',   'Users', 'high'),
            'suspend':  ('suspend',  'Users', 'high'),
            'activate': ('activate', 'Users', 'low'),
            'password': ('password', 'Users', 'high'),
            'import':   ('import',   'Users', 'medium'),
            'export':   ('export',   'Users', 'low'),
            'security': ('security', 'Auth',  'medium'),
        }

        qs = UserActivityLog.objects.select_related(
            'actor', 'actor__profile',
            'target_user', 'target_user__profile',
        ).order_by('-timestamp')

        if filters:
            action_f = filters.get('action')
            if action_f and action_f != 'all':
                actions = action_f.split(',')
                matching = [k for k, v in ACTION_MAP.items() if v[0] in actions]
                if not matching:
                    return []
                qs = qs.filter(action__in=matching)

            module_f = filters.get('module')
            if module_f and module_f != 'all' and module_f != 'Users' and module_f != 'Auth':
                return []

            severity_f = filters.get('severity')
            if severity_f and severity_f != 'all':
                sev_actions = [k for k, v in ACTION_MAP.items() if v[2] == severity_f]
                if not sev_actions:
                    return []
                qs = qs.filter(action__in=sev_actions)

            if filters.get('date_from'):
                qs = qs.filter(timestamp__date__gte=filters['date_from'])
            if filters.get('date_to'):
                qs = qs.filter(timestamp__date__lte=filters['date_to'])
            if filters.get('search'):
                s = filters['search']
                qs = qs.filter(Q(description__icontains=s))

        results = []
        for row in qs:
            action_key              = row.action or 'update'
            audit_action, mod, sev  = ACTION_MAP.get(action_key, ('update', 'Users', 'low'))

            actor    = row.actor
            profile  = getattr(actor, 'profile', None) if actor else None
            name     = profile.full_name if profile else (actor.email if actor else 'System')
            initials = (profile.avatar_initials if profile else
                        (name[:2].upper() if name else 'SY'))

            role = ''
            if actor:
                try:
                    ur = actor.user_roles.filter(is_active=True).select_related('role').first()
                    role = ur.role.name if ur else ''
                except Exception:
                    pass

            results.append({
                'id':            f'al-{row.pk}',
                'user':          actor.pk if actor else None,
                'user_name':     name,
                'user_initials': initials,
                'user_role':     role,
                'user_snapshot': {
                    'name':     name,
                    'email':    actor.email if actor else '',
                    'initials': initials,
                },
                'action':        audit_action,
                'module':        mod,
                'entity':        row.description or f'{audit_action.title()} action',
                'ip_address':    '',
                'city':          '',
                'device_info':   '',
                'before_data':   None,
                'after_data':    None,
                'severity':      sev,
                'timestamp':     row.timestamp.isoformat() if row.timestamp else None,
                'ts':            row.timestamp.strftime("%Y-%m-%d %H:%M:%S") if row.timestamp else '',
            })
        return results
    except Exception:
        return []


def get_audit_logs(filters: dict = None) -> list:
    """
    Returns a merged, sorted list of dicts from:
      1. AuditLog        (new — written going forward)
      2. LoginLog        (existing login history)
      3. UserActivityLog (existing user management actions)
    """
    # ── 1. New AuditLog rows ──
    audit_dicts = []
    for row in _get_audit_qs(filters):
        p        = getattr(row.user, 'profile', None) if row.user else None
        name     = (row.user_snapshot.get('name') if row.user_snapshot else None or
                    (p.full_name if p else '') or
                    (row.user.email if row.user else 'System'))
        initials = (row.user_snapshot.get('initials') if row.user_snapshot else None or
                    (p.avatar_initials if p else '') or
                    name[:2].upper() or 'SY')
        audit_dicts.append({
            'id':            row.pk,
            'user':          row.user_id,
            'user_name':     name,
            'user_initials': initials,
            'user_role':     row.role_at_time or '',
            'user_snapshot': row.user_snapshot,
            'action':        row.action,
            'module':        row.module,
            'entity':        row.entity,
            'ip_address':    row.ip_address or '',
            'city':          row.city or '',
            'device_info':   row.device_info or '',
            'before_data':   row.before_data,
            'after_data':    row.after_data,
            'severity':      row.severity,
            'timestamp':     row.timestamp.isoformat() if row.timestamp else None,
            'ts':            row.timestamp.strftime("%Y-%m-%d %H:%M:%S") if row.timestamp else '',
        })

    # ── 2 & 3. Legacy tables ──
    login_dicts    = _login_logs_as_dicts(filters)
    activity_dicts = _activity_logs_as_dicts(filters)

    # ── Merge & sort by timestamp desc ──
    merged = list(chain(audit_dicts, login_dicts, activity_dicts))
    merged.sort(key=lambda x: x['timestamp'] or '', reverse=True)
    
    # ✅ ADDED: Support for Change History (has_diff filter)
    if filters and filters.get('has_diff') == 'true':
        merged = [l for l in merged if l.get('before_data') or l.get('after_data')]
        
    return merged


def get_audit_stats() -> dict:
    """Today's severity counts merged across all three sources."""
    today  = timezone.now().date()
    
    # Base Querysets
    audit_qs = AuditLog.objects.all()
    try:
        from crmapp.system.auth_security.models import LoginLog
        login_qs = LoginLog.objects.all()
    except Exception:
        login_qs = AuditLog.objects.none()
        
    try:
        from crmapp.system.usermanage.models import UserActivityLog
        act_qs = UserActivityLog.objects.all()
    except Exception:
        act_qs = AuditLog.objects.none()

    total = audit_qs.count() + login_qs.count() + act_qs.count()
    today_count = audit_qs.filter(timestamp__date=today).count() + \
                  login_qs.filter(timestamp__date=today).count() + \
                  act_qs.filter(timestamp__date=today).count()
    
    # High Severity
    audit_high = audit_qs.filter(severity__in=['high', 'critical']).count()
    login_fail = login_qs.filter(status__in=['failed', 'locked']).count()
    act_high = act_qs.filter(action__in=['delete', 'suspend', 'password']).count()
    high_total = audit_high + login_fail + act_high
    
    # Login Stats
    login_success = login_qs.filter(status='success').count()
    unique_ips = login_qs.values('ip_address').distinct().count()
    
    # Deletions
    deletions = act_qs.filter(action='delete').count() + audit_qs.filter(action='delete').count()
    
    # Action Freq
    action_counts = {}
    for log in audit_qs:
        action_counts[log.action] = action_counts.get(log.action, 0) + 1
    for log in act_qs:
        action_counts[log.action] = action_counts.get(log.action, 0) + 1
    action_counts['login'] = login_success
    action_counts['login_fail'] = login_fail
    
    action_freq = [{"action": k, "count": v} for k, v in sorted(action_counts.items(), key=lambda item: item[1], reverse=True)]
    
    # Module Freq
    module_counts = {}
    for log in audit_qs:
        module_counts[log.module] = module_counts.get(log.module, 0) + 1
    module_counts['Users'] = module_counts.get('Users', 0) + act_qs.count()
    module_counts['Auth'] = module_counts.get('Auth', 0) + login_qs.count()
    module_freq = [{"module": k, "count": v} for k, v in sorted(module_counts.items(), key=lambda item: item[1], reverse=True)]
    
    # User Activity (Top 5)
    user_counts = {}
    for log in audit_qs:
        if log.user:
            uname = log.user.username
            user_counts[uname] = user_counts.get(uname, 0) + 1
    for log in act_qs:
        if log.actor:
            uname = log.actor.username
            user_counts[uname] = user_counts.get(uname, 0) + 1
            
    user_activity = [{"user": k, "avatar": k[:2].upper(), "count": v} for k, v in sorted(user_counts.items(), key=lambda item: item[1], reverse=True)[:5]]
    
    return {
        "total": total,
        "today": today_count,
        "high": high_total,
        "login_failures": login_fail,
        "deletions": deletions,
        "action_freq": action_freq,
        "module_freq": module_freq,
        "user_activity": user_activity,
        "severity_counts": {
            "high": high_total,
            "medium": act_qs.filter(action__in=['create', 'import']).count() + audit_qs.filter(severity='medium').count(),
            "low": act_qs.exclude(action__in=['delete', 'suspend', 'password', 'create', 'import']).count() + audit_qs.filter(severity='low').count() + login_success
        },
        "login_stats": {
            "success": login_success,
            "failed": login_fail,
            "logout": 0,
            "unique_ips": unique_ips
        },
        "permission_changes": act_qs.filter(action__in=['role', 'security']).count(),
        "security_events": act_qs.filter(action='security').count() + audit_qs.filter(action='security').count()
    }