"""
backend/__init__.py

This makes Celery load automatically when Django starts.
Place this in the same folder as settings.py and celery.py.
"""

from .celery import app as celery_app

__all__ = ("celery_app",)