from .models import PayrollRun, PayrollLine

def create_payroll_run(month, user=None):
    return PayrollRun.objects.create(month=month, status="draft", created_by=user)

def add_payroll_line(run, employee, basic, allowances=0, deductions=0, tax=0):
    net_pay = basic + allowances - deductions - tax
    line = PayrollLine.objects.create(run=run, employee=employee, basic=basic, allowances=allowances, deductions=deductions, tax=tax, net_pay=net_pay)
    _recalc(run)
    return line

def _recalc(run):
    lines = run.lines.all()
    run.total_gross = sum(l.basic + l.allowances for l in lines)
    run.total_tax   = sum(l.tax for l in lines)
    run.total_net   = sum(l.net_pay for l in lines)
    run.save(update_fields=["total_gross", "total_tax", "total_net", "updated_at"])

def approve_run(run):
    if run.status != "draft": raise ValueError("Only draft payroll runs can be approved.")
    run.status = "approved"; run.save(update_fields=["status", "updated_at"]); return run

def mark_paid(run):
    if run.status != "approved": raise ValueError("Only approved payroll runs can be marked as paid.")
    run.status = "paid"; run.save(update_fields=["status", "updated_at"]); return run