"""`apps/core/tasks.py` — davriy fon vazifalari.

Testlar Celery brokersiz ishlaydi: `conftest.py` dagi `_celery_always_eager`
fixture'i `task_always_eager` ni majburlaydi, ya'ni `.delay()` ham shu
jarayonda bajariladi. Shu sababli bu yerda "vazifa navbatga tushdimi" emas,
uning NATIJASI tekshiriladi.
"""

import inspect
from datetime import timedelta

import pytest
from django.apps import apps as django_apps
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone

from apps.core.enums import TaskStatus
from apps.core.models import SoftDeleteModel
from apps.core.tasks import (
    SOFT_DELETE_MODELS,
    flush_expired_tokens,
    purge_soft_deleted,
)

RETENTION = 30


def make_task(env, title="Vazifa", position="n"):
    from apps.tasks.models import Task

    return Task.objects.create(
        list=env.list,
        status=TaskStatus.TODO,
        title=title,
        position=position,
        created_by=env.owner,
    )


def make_comment(task, author):
    from apps.comments.models import Comment

    return Comment.objects.create(task=task, author=author, body_html="<p>salom</p>")


def make_message(env, author):
    from apps.chat.models import Conversation, Message

    conversation = Conversation.objects.create(
        workspace=env.workspace, kind="channel", name="umumiy", created_by=author
    )
    return Message.objects.create(conversation=conversation, author=author, body="salom")


def soft_delete_at(instance, *, days_ago):
    """Qatorni soft-delete qilib, `deleted_at` ni o'tmishga suradi."""
    instance.delete()
    type(instance).all_objects.filter(pk=instance.pk).update(
        deleted_at=timezone.now() - timedelta(days=days_ago)
    )
    return instance


# ---------------------------------------------------------------------------
# Ro'yxatning to'liqligi
# ---------------------------------------------------------------------------


def test_every_soft_delete_model_is_covered():
    """`SoftDeleteModel` dan meros olgan HAR BIR model tozalanishi shart.

    Aks holda yangi soft-delete model qo'shilganda uning qatorlari jimgina
    abadiy qolib ketardi — aynan ADR 0003 ko'rsatgan bo'shliq.
    """
    discovered = {
        f"{model._meta.app_label}.{model.__name__}"
        for model in django_apps.get_models()
        if issubclass(model, SoftDeleteModel)
    }
    assert discovered == set(SOFT_DELETE_MODELS)


def test_listed_models_resolve_and_have_all_objects():
    for label in SOFT_DELETE_MODELS:
        model = django_apps.get_model(label)
        assert hasattr(model, "all_objects"), label


# ---------------------------------------------------------------------------
# purge_soft_deleted
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_purge_removes_rows_past_retention(env):
    from apps.tasks.models import Task

    stale = soft_delete_at(make_task(env, "Eski", position="a"), days_ago=RETENTION + 1)
    fresh = soft_delete_at(make_task(env, "Yangi", position="b"), days_ago=1)
    alive = make_task(env, "Tirik", position="c")

    result = purge_soft_deleted(retention_days=RETENTION)

    assert result["tasks.Task"] == 1
    assert not Task.all_objects.filter(pk=stale.pk).exists()
    assert Task.all_objects.filter(pk=fresh.pk).exists()
    assert Task.objects.filter(pk=alive.pk).exists()


@pytest.mark.django_db
def test_purge_keeps_the_row_exactly_on_the_boundary(env):
    """Chegara QAT'IY `<`: muddati aynan to'lgan qator hali saqlanadi.

    Bu "bir kun erta o'chib ketdi" xatosining yagona himoyasi.
    """
    from apps.tasks.models import Task

    task = make_task(env, "Chegara", position="a")
    task.delete()
    # Vazifa cutoff'ni O'ZI hisoblaydi (`now() - days`), ya'ni bu satr bilan
    # tekshiruv orasida o'tgan vaqt cutoff'ni oldinga suradi. Chegarani
    # sekundlik zaxira bilan qo'yamiz: qator hali muddat ICHIDA.
    boundary = timezone.now() - timedelta(days=RETENTION) + timedelta(seconds=5)
    Task.all_objects.filter(pk=task.pk).update(deleted_at=boundary)

    assert purge_soft_deleted(retention_days=RETENTION)["tasks.Task"] == 0
    assert Task.all_objects.filter(pk=task.pk).exists()


@pytest.mark.django_db
def test_purge_never_touches_alive_rows(env):
    from apps.tasks.models import Task

    alive = [make_task(env, f"Tirik {i}", position=chr(97 + i)) for i in range(3)]

    assert purge_soft_deleted(retention_days=0)["tasks.Task"] == 0
    assert purge_soft_deleted(retention_days=RETENTION)["tasks.Task"] == 0
    assert Task.objects.filter(pk__in=[t.pk for t in alive]).count() == 3


@pytest.mark.django_db
def test_purge_is_disabled_when_retention_is_not_positive(env):
    """`SOFT_DELETE_RETENTION_DAYS=0` "hammasini hoziroq o'chir" DEGANI EMAS."""
    from apps.tasks.models import Task

    stale = soft_delete_at(make_task(env, "Eski", position="a"), days_ago=999)

    assert purge_soft_deleted(retention_days=0) == {label: 0 for label in SOFT_DELETE_MODELS}
    assert purge_soft_deleted(retention_days=-5)["tasks.Task"] == 0
    assert Task.all_objects.filter(pk=stale.pk).exists()


@pytest.mark.django_db
def test_purge_walks_batches(env):
    """Partiya hajmi qatorlar sonidan kichik bo'lsa ham hammasi o'chadi."""
    from apps.tasks.models import Task

    for i in range(5):
        soft_delete_at(make_task(env, f"Eski {i}", position=chr(97 + i)), days_ago=RETENTION + 2)

    assert purge_soft_deleted(retention_days=RETENTION, batch_size=2)["tasks.Task"] == 5
    assert Task.all_objects.count() == 0


@pytest.mark.django_db
def test_purge_covers_comments_and_messages(env):
    from apps.chat.models import Message
    from apps.comments.models import Comment

    task = make_task(env, "Ota vazifa", position="a")
    comment = soft_delete_at(make_comment(task, env.owner), days_ago=RETENTION + 1)
    message = soft_delete_at(make_message(env, env.owner), days_ago=RETENTION + 1)

    result = purge_soft_deleted(retention_days=RETENTION)

    assert result["comments.Comment"] == 1
    assert result["chat.Message"] == 1
    assert not Comment.all_objects.filter(pk=comment.pk).exists()
    assert not Message.all_objects.filter(pk=message.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_purge_removes_attachment_files_from_disk(env):
    """ADR 0003 sanagan salbiy oqibat: yetim biriktirma fayllari.

    Vazifa qattiq o'chganda CASCADE `TaskAttachment` QATORINI oladi, lekin
    Django diskdagi faylni hech qachon o'chirmaydi. Tozalash uni ham olishi
    shart, aks holda `media/` cheksiz o'sadi.
    """
    from apps.tasks.models import TaskAttachment

    task = make_task(env, "Biriktirmali", position="a")
    attachment = TaskAttachment(
        task=task,
        original_name="hisobot.txt",
        content_type="text/plain",
        size_bytes=5,
        uploaded_by=env.owner,
    )
    attachment.file.save(
        "purge-test.txt", SimpleUploadedFile("purge-test.txt", b"salom"), save=False
    )
    attachment.save()
    storage, name = attachment.file.storage, attachment.file.name
    assert name is not None
    assert storage.exists(name)

    soft_delete_at(task, days_ago=RETENTION + 1)
    purge_soft_deleted(retention_days=RETENTION)

    assert not TaskAttachment.objects.filter(pk=attachment.pk).exists()
    assert not storage.exists(name), "biriktirma fayli diskda qolib ketdi"


@pytest.mark.django_db
def test_purge_runs_through_celery_delay(env):
    """Eager rejimda `.delay()` brokersiz ishlaydi va natijani qaytaradi."""
    from apps.tasks.models import Task

    stale = soft_delete_at(make_task(env, "Eski", position="a"), days_ago=RETENTION + 1)

    result = purge_soft_deleted.delay(retention_days=RETENTION)

    assert result.successful()
    assert result.get()["tasks.Task"] == 1
    assert not Task.all_objects.filter(pk=stale.pk).exists()


@pytest.mark.django_db
def test_purge_defaults_to_the_configured_retention(env, settings):
    from apps.tasks.models import Task

    settings.SOFT_DELETE_RETENTION_DAYS = 7
    keep = soft_delete_at(make_task(env, "5 kun", position="a"), days_ago=5)
    drop = soft_delete_at(make_task(env, "9 kun", position="b"), days_ago=9)

    assert purge_soft_deleted()["tasks.Task"] == 1
    assert Task.all_objects.filter(pk=keep.pk).exists()
    assert not Task.all_objects.filter(pk=drop.pk).exists()


# ---------------------------------------------------------------------------
# Management buyrug'i
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_management_command_is_dry_run_by_default(env):
    from apps.tasks.models import Task

    stale = soft_delete_at(make_task(env, "Eski", position="a"), days_ago=RETENTION + 1)

    call_command("purge_soft_deleted", "--days", str(RETENTION))
    assert Task.all_objects.filter(pk=stale.pk).exists()

    call_command("purge_soft_deleted", "--days", str(RETENTION), "--yes")
    assert not Task.all_objects.filter(pk=stale.pk).exists()


# ---------------------------------------------------------------------------
# flush_expired_tokens
# ---------------------------------------------------------------------------


def _outstanding(user, *, expires_in_days, jti):
    OutstandingToken = django_apps.get_model("token_blacklist", "OutstandingToken")
    return OutstandingToken.objects.create(
        user=user,
        jti=jti,
        token="dummy",
        created_at=timezone.now() - timedelta(days=1),
        expires_at=timezone.now() + timedelta(days=expires_in_days),
    )


@pytest.mark.django_db
def test_flush_expired_tokens_removes_only_expired_rows(env):
    OutstandingToken = django_apps.get_model("token_blacklist", "OutstandingToken")
    OutstandingToken.objects.all().delete()

    expired = _outstanding(env.owner, expires_in_days=-1, jti="expired-1")
    valid = _outstanding(env.owner, expires_in_days=7, jti="valid-1")

    assert flush_expired_tokens() == 1
    assert not OutstandingToken.objects.filter(pk=expired.pk).exists()
    assert OutstandingToken.objects.filter(pk=valid.pk).exists()


@pytest.mark.django_db
def test_flush_expired_tokens_cascades_to_the_blacklist(env):
    BlacklistedToken = django_apps.get_model("token_blacklist", "BlacklistedToken")
    OutstandingToken = django_apps.get_model("token_blacklist", "OutstandingToken")
    OutstandingToken.objects.all().delete()

    expired = _outstanding(env.owner, expires_in_days=-3, jti="expired-2")
    BlacklistedToken.objects.create(token=expired)

    assert flush_expired_tokens(batch_size=1) == 1
    assert BlacklistedToken.objects.count() == 0


@pytest.mark.django_db
def test_flush_expired_tokens_walks_batches(env):
    OutstandingToken = django_apps.get_model("token_blacklist", "OutstandingToken")
    OutstandingToken.objects.all().delete()
    for i in range(5):
        _outstanding(env.owner, expires_in_days=-2, jti=f"expired-batch-{i}")

    assert flush_expired_tokens(batch_size=2) == 5
    assert OutstandingToken.objects.count() == 0


@pytest.mark.django_db
def test_flush_expired_tokens_is_a_noop_on_an_empty_table():
    OutstandingToken = django_apps.get_model("token_blacklist", "OutstandingToken")
    OutstandingToken.objects.all().delete()
    assert flush_expired_tokens() == 0


# ---------------------------------------------------------------------------
# Ro'yxatga olish (registry)
# ---------------------------------------------------------------------------


def test_tasks_are_registered_with_stable_names():
    """Beat jadvali vazifalarni NOM bo'yicha chaqiradi — nom o'zgarsa jimgina o'lik.

    `CELERY_BEAT_SCHEDULE` dagi har bir nom haqiqatan ro'yxatdan o'tgan
    bo'lishi shart.
    """
    from django.conf import settings as django_settings

    from config.celery import app as celery_app

    scheduled = {entry["task"] for entry in django_settings.CELERY_BEAT_SCHEDULE.values()}
    assert scheduled <= set(celery_app.tasks)
    assert {"core.purge_soft_deleted", "core.flush_expired_tokens"} <= scheduled


def test_tasks_live_where_autodiscovery_looks_for_them():
    """`autodiscover_tasks()` har bir ilovada AYNAN `tasks` modulini qidiradi.

    Modul boshqa nomga ko'chirilsa (masalan `jobs.py`) hamma narsa lokal
    testda ishlaydi — chunki test uni o'zi import qiladi — lekin haqiqiy
    worker vazifalarni umuman ko'rmay qoladi. Shu sabab yo'l tekshiriladi.
    """
    from django.conf import settings as django_settings

    import apps.core.tasks as module

    assert module.__name__ == "apps.core.tasks"
    assert "apps.core" in django_settings.INSTALLED_APPS


def test_task_signatures_accept_no_required_arguments():
    """Beat vazifani argumentsiz chaqiradi — majburiy parametr bo'lmasin."""
    for task in (purge_soft_deleted, flush_expired_tokens):
        signature = inspect.signature(task.run)
        required = [
            name
            for name, param in signature.parameters.items()
            if param.default is inspect.Parameter.empty
        ]
        assert required == [], f"{task.name}: {required}"
