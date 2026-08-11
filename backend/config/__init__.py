"""`config` paketi.

Celery ilovasi SHU YERDA import qilinadi, chunki `@shared_task` bilan
e'lon qilingan har bir vazifa "joriy ilova" ni topishi kerak — Django
ishga tushganda (`manage.py`, `wsgi.py`, `asgi.py` — hammasi `config.settings`
ni import qiladi, ya'ni shu paketni) ilova allaqachon ro'yxatdan o'tgan
bo'ladi. Import yengil: ulanish ochilmaydi, sozlama lazy o'qiladi.
"""

from config.celery import app as celery_app

__all__ = ["celery_app"]
