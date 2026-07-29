# settings_config/services.py
from django.utils import timezone
from django.db import transaction
from .models import SystemSetting, NotificationSetting, EmailConfig, IntegrationKey, BackupRecord


def get_system_setting():      return SystemSetting.get()
def get_notification_setting(): return NotificationSetting.get()
def get_email_config():         return EmailConfig.get()


def update_system_setting(data: dict, actor=None) -> SystemSetting:
    s = SystemSetting.get()
    for k, v in data.items():
        if hasattr(s, k): setattr(s, k, v)
    s.updated_by = actor
    s.save()
    _log('System settings updated', actor)
    return s


def update_notification_setting(data: dict, actor=None) -> NotificationSetting:
    n = NotificationSetting.get()
    for k, v in data.items():
        if hasattr(n, k): setattr(n, k, v)
    n.save()
    _log('Notification settings updated', actor)
    return n


def update_email_config(data: dict, actor=None) -> EmailConfig:
    c = EmailConfig.get()
    for k, v in data.items():
        if hasattr(c, k): setattr(c, k, v)
    c.is_verified = False
    c.save()
    _log('Email config updated', actor)
    return c


def test_email_config() -> bool:
    import smtplib
    c = EmailConfig.get()
    try:
        if c.encryption == 'ssl':
            srv = smtplib.SMTP_SSL(c.smtp_host, c.smtp_port, timeout=10)
        else:
            srv = smtplib.SMTP(c.smtp_host, c.smtp_port, timeout=10)
            if c.encryption == 'tls': srv.starttls()
        srv.login(c.smtp_user, c.smtp_password)
        srv.quit()
        c.is_verified = True
        c.save(update_fields=['is_verified'])
        return True
    except Exception:
        return False


def get_integration_keys():
    return IntegrationKey.objects.all().order_by('name')


def create_integration_key(data: dict, actor=None) -> IntegrationKey:
    key = IntegrationKey.objects.create(**data)
    _log(f'Integration key added: {key.name}', actor)
    return key


def update_integration_key(key: IntegrationKey, data: dict, actor=None) -> IntegrationKey:
    for k, v in data.items():
        if hasattr(key, k): setattr(key, k, v)
    key.save()
    _log(f'Integration key updated: {key.name}', actor)
    return key


def delete_integration_key(key: IntegrationKey, actor=None):
    name = key.name
    key.delete()
    _log(f'Integration key deleted: {name}', actor)


def get_backup_records():
    return BackupRecord.objects.select_related(
        'initiated_by', 'initiated_by__profile'
    ).order_by('-created_at')


@transaction.atomic
def run_manual_backup(actor=None) -> BackupRecord:
    from datetime import datetime
    name   = f'manual_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    record = BackupRecord.objects.create(
        name=name, backup_type='manual',
        status='running', initiated_by=actor, size_display='Calculating...',
    )
    _log(f'Manual backup initiated: {name}', actor)
    # TODO: dispatch celery task → run_backup.delay(record.pk)
    return record


def mark_backup_complete(record: BackupRecord, size_display: str, file_path: str):
    record.status       = 'completed'
    record.size_display = size_display
    record.file_path    = file_path
    record.completed_at = timezone.now()
    record.save()


def _log(entity: str, actor=None):
    try:
        from audit.services import log_event
        log_event(user=actor, action='settings', module='Settings',
                  entity=entity, severity='low')
    except Exception:
        pass