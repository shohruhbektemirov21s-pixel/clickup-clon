"""Celery ilovasi — fon vazifalar qatlami.

Loyihaning ASOSIY dev yo'li Redis'siz ishlaydi (CLAUDE.md: "Redis ixtiyoriy").
Shuning uchun bu yerda hech qanday ulanish OCHILMAYDI: `Celery(...)` obyekti
yaratiladi, konfiguratsiya esa `django.conf:settings` dan LAZY o'qiladi.
Broker'ga birinchi murojaat faqat vazifa navbatga qo'yilganda bo'ladi, va
`CELERY_TASK_ALWAYS_EAGER` yoqilgan bo'lsa (broker manzili bo'sh — qarang
`config/settings.py`) umuman bo'lmaydi: vazifa chaqirilgan joyda, o'sha
jarayonda, sinxron bajariladi.

Ishga tushirish (broker bor bo'lganda, `backend/` dan):

    ../.venv/Scripts/python.exe -m celery -A config worker -l info
    ../.venv/Scripts/python.exe -m celery -A config beat -l info

`-A config` — bu modul emas, PAKET: Celery `config.celery.app` ni
`config/__init__.py` dagi `celery_app` orqali topadi.
"""

from __future__ import annotations

import os

from celery import Celery

# `celery -A config worker` Django'ni o'zi ko'tarmaydi — settings modulini
# shu yerda ko'rsatib qo'yamiz, aks holda worker `ImproperlyConfigured` beradi.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("uzwork")

# Barcha sozlamalar Django settings'dagi `CELERY_` prefiksli kalitlardan
# olinadi — ya'ni yagona manba `backend/.env` bo'lib qoladi, alohida
# `celeryconfig.py` yo'q. `namespace` tufayli `CELERY_BROKER_URL` ->
# `broker_url`.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Har bir INSTALLED_APPS ilovasining `tasks` modulini qidiradi
# (`apps/core/tasks.py` va h.k.). Django app registry tayyor bo'lgandan
# keyin ishga tushadigan lazy chaqiruv.
app.autodiscover_tasks()


@app.task(bind=True, name="core.debug_ping")
def debug_ping(self) -> str:
    """Worker → broker zanjiri tirikligini tekshirish uchun eng arzon vazifa.

    Hech qanday DB'ga tegmaydi; deploy'dan keyin `debug_ping.delay()` bilan
    "worker haqiqatan ham navbatni o'qiyaptimi" degan savolga javob beradi.
    """
    return f"pong from {self.request.hostname or 'eager'}"
