import pytest

from apps.comments.models import Comment
from apps.tasks.models import Task
from conftest import assert_error

pytestmark = pytest.mark.django_db

DOC = {"type": "doc", "content": []}


@pytest.fixture
def task(env):
    response = env.member_client.post(
        f"/api/v1/lists/{env.list.id}/tasks/", {"title": "Discussable"}, format="json"
    )
    return response.json()


def comments_url(task_id):
    return f"/api/v1/tasks/{task_id}/comments/"


def comment_url(comment_id):
    return f"/api/v1/comments/{comment_id}/"


def post_comment(client, task_id, html="<p>hello</p>", **extra):
    return client.post(
        comments_url(task_id), {"body_html": html, "body_json": DOC, **extra}, format="json"
    )


def test_create_comment_and_count(env, task):
    response = post_comment(env.guest_client, task["id"])  # guests may comment
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["body_html"] == "<p>hello</p>"
    assert body["parent_id"] is None
    assert body["author"]["id"] == str(env.guest.id)
    assert Task.objects.get(pk=task["id"]).comment_count == 1
    # commenting auto-adds the watcher
    detail = env.member_client.get(f"/api/v1/tasks/{task['id']}/").json()
    assert str(env.guest.id) in [w["id"] for w in detail["watchers"]]


def test_both_body_fields_required(env, task):
    response = env.member_client.post(
        comments_url(task["id"]), {"body_html": "<p>x</p>"}, format="json"
    )
    assert_error(response, 400, "validation_error")

    empty = post_comment(env.member_client, task["id"], html="<script>x</script>")
    assert_error(empty, 400, "validation_error")  # empty after sanitisation


def test_replies_are_depth_one(env, task):
    parent = post_comment(env.member_client, task["id"]).json()
    reply = post_comment(env.member_client, task["id"], parent_id=parent["id"])
    assert reply.status_code == 201
    assert reply.json()["parent_id"] == parent["id"]
    assert Comment.objects.get(pk=parent["id"]).reply_count == 1

    nested = post_comment(env.member_client, task["id"], parent_id=reply.json()["id"])
    assert_error(nested, 400, "validation_error")

    other_task = env.member_client.post(
        f"/api/v1/lists/{env.list.id}/tasks/", {"title": "Other"}, format="json"
    ).json()
    cross = post_comment(env.member_client, other_task["id"], parent_id=parent["id"])
    assert_error(cross, 400, "validation_error")


def test_edit_is_author_only(env, task):
    comment = post_comment(env.member_client, task["id"]).json()
    denied = env.admin_client.patch(
        comment_url(comment["id"]),
        {"body_html": "<p>hijack</p>", "body_json": DOC},
        format="json",
    )
    assert_error(denied, 403, "permission_denied")  # admins may NOT edit others'

    edited = env.member_client.patch(
        comment_url(comment["id"]),
        {"body_html": "<p>edited</p>", "body_json": DOC},
        format="json",
    )
    assert edited.status_code == 200
    assert edited.json()["is_edited"] is True
    assert edited.json()["edited_at"] is not None


def test_delete_author_or_admin(env, task):
    comment = post_comment(env.guest_client, task["id"]).json()

    denied = env.member_client.delete(comment_url(comment["id"]))
    assert_error(denied, 403, "permission_denied")

    ok = env.admin_client.delete(comment_url(comment["id"]))  # admin+ may delete anyone's
    assert ok.status_code == 204
    assert Task.objects.get(pk=task["id"]).comment_count == 0

    listing = env.member_client.get(comments_url(task["id"])).json()
    assert listing["count"] == 0  # soft-deleted comments excluded


def test_deleted_parent_keeps_replies(env, task):
    parent = post_comment(env.member_client, task["id"]).json()
    reply = post_comment(env.guest_client, task["id"], parent_id=parent["id"]).json()
    env.member_client.delete(comment_url(parent["id"]))

    listing = env.member_client.get(comments_url(task["id"])).json()
    ids = [c["id"] for c in listing["results"]]
    assert reply["id"] in ids
    assert parent["id"] not in ids


def test_comment_pagination_is_chronological(env, task):
    for i in range(3):
        post_comment(env.member_client, task["id"], html=f"<p>c{i}</p>")
    listing = env.member_client.get(comments_url(task["id"])).json()
    assert [c["body_html"] for c in listing["results"]] == ["<p>c0</p>", "<p>c1</p>", "<p>c2</p>"]
    assert set(listing.keys()) == {"count", "next", "previous", "results"}
