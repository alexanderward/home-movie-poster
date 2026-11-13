from io import BytesIO

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client
from PIL import Image

from apps.server.apps.posters.models import (
    ApplicationSettings,
    Collection,
    CollectionItem,
    Movie,
    PosterAsset,
)
from apps.server.apps.posters.selectors import display_state
from apps.server.apps.posters.services import (
    ConflictError,
    add_to_collection,
    create_collection,
    delete_collection,
    rename_collection,
    set_active_collection,
)

pytestmark = pytest.mark.django_db(transaction=True)


def item(title):
    asset = PosterAsset.objects.create(path=f"posters/{title}.jpg", width=100, height=150)
    return Movie.objects.create(
        source=Movie.Source.MANUAL,
        source_key=title,
        title=title,
        normalized_title=title.casefold(),
        poster=asset,
    )


def api_client():
    client = Client(enforce_csrf_checks=True)
    token = client.get("/api/session").json()["csrf_token"]
    return client, {"HTTP_X_CSRFTOKEN": token}


def test_first_collection_becomes_active_and_names_are_unique():
    first = create_collection("Movies")
    create_collection("Artwork")
    assert ApplicationSettings.load().active_collection_id == first.id
    with pytest.raises(ConflictError):
        create_collection("  movies ")
    with pytest.raises(ConflictError):
        rename_collection(first.id, "ARTWORK")


def test_slideshow_rotates_only_the_active_collection():
    movies = create_collection("Movies")
    art = create_collection("Artwork")
    add_to_collection(movies.id, item("Heat").id)
    add_to_collection(art.id, item("Water Lilies").id)

    state = display_state()
    assert (state.mode, state.headline, state.title) == ("rotation", "Movies", "Heat")

    set_active_collection(art.id)
    state = display_state()
    assert (state.headline, state.title) == ("Artwork", "Water Lilies")

    set_active_collection(None)
    assert display_state().mode == "setup"


def test_collection_tv_headline_overrides_or_hides_the_name():
    client, headers = api_client()
    movies = create_collection("Movies")
    add_to_collection(movies.id, item("Heat").id)

    response = client.patch(
        f"/api/collections/{movies.id}",
        data={"tv_headline": "  Now Showing "},
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["tv_headline"], body["show_headline"]) == ("Movies", "Now Showing", True)
    assert display_state().headline == "Now Showing"

    client.patch(
        f"/api/collections/{movies.id}",
        data={"show_headline": False},
        content_type="application/json",
        **headers,
    )
    assert display_state().headline == ""

    client.patch(
        f"/api/collections/{movies.id}",
        data={"tv_headline": "", "show_headline": True},
        content_type="application/json",
        **headers,
    )
    assert display_state().headline == "Movies"


def test_items_belong_to_several_collections_and_survive_collection_deletion():
    shared = item("Alien")
    sci_fi = create_collection("Sci-Fi")
    favorites = create_collection("Favorites")
    add_to_collection(sci_fi.id, shared.id)
    add_to_collection(favorites.id, shared.id)
    add_to_collection(favorites.id, shared.id)  # Adding twice is a no-op.
    assert CollectionItem.objects.filter(movie=shared).count() == 2

    delete_collection(sci_fi.id)
    assert Movie.objects.filter(pk=shared.pk).exists()
    assert list(shared.collections.values_list("name", flat=True)) == ["Favorites"]
    # Deleting the active collection leaves the TV without a slideshow until one is chosen.
    assert ApplicationSettings.load().active_collection_id is None


def test_collection_api_round_trip():
    client, csrf = api_client()
    created = client.post(
        "/api/collections", {"name": "Holiday"}, content_type="application/json", **csrf
    )
    assert created.status_code == 201
    collection_id = created.json()["id"]
    assert created.json()["active"] is True

    upload = BytesIO()
    Image.new("RGB", (60, 90), (200, 30, 30)).save(upload, "PNG")
    upload.seek(0)
    upload.name = "card.png"
    uploaded = client.post(
        "/api/movies/manual",
        {"title": "Holiday Card", "collection_id": str(collection_id), "poster": upload},
        **csrf,
    )
    assert uploaded.status_code == 201
    movie_id = uploaded.json()["id"]
    assert uploaded.json()["collection_ids"] == [collection_id]

    other = client.post(
        "/api/collections", {"name": "Family"}, content_type="application/json", **csrf
    ).json()["id"]
    added = client.put(f"/api/collections/{other}/items/{movie_id}", **csrf)
    assert sorted(added.json()["collection_ids"]) == sorted([collection_id, other])

    detail = client.get(f"/api/collections/{collection_id}").json()
    assert (detail["item_count"], [row["title"] for row in detail["items"]]) == (
        1,
        ["Holiday Card"],
    )
    assert detail["cover_url"].startswith("/media/")

    listing = client.put(
        "/api/collections/active",
        {"collection_id": other},
        content_type="application/json",
        **csrf,
    ).json()
    assert listing["active_id"] == other
    assert [row["name"] for row in listing["items"]] == ["Family", "Holiday"]

    assert client.delete(f"/api/collections/{other}/items/{movie_id}", **csrf).status_code == 204
    assert client.get(f"/api/collections/{other}").json()["item_count"] == 0
    assert client.put(f"/api/collections/{other}/items/{movie_id}").status_code == 403
    duplicate = client.patch(
        f"/api/collections/{other}",
        {"name": "holiday"},
        content_type="application/json",
        **csrf,
    )
    assert duplicate.status_code == 409


def test_migration_moves_slideshow_flags_into_an_active_movies_collection():
    executor = MigrationExecutor(connection)
    executor.migrate([("posters", "0002_monitorheartbeat_delete_librarysync_and_more")])
    old = executor.loader.project_state(
        [("posters", "0002_monitorheartbeat_delete_librarysync_and_more")]
    ).apps
    OldMovie = old.get_model("posters", "Movie")
    OldMovie.objects.create(
        source="manual", source_key="a", title="In", normalized_title="in", include_in_rotation=True
    )
    OldMovie.objects.create(
        source="manual", source_key="b", title="Out", normalized_title="out", include_in_rotation=False
    )

    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    # Migrate all the way forward so the current models (and later tests) see the latest schema.
    executor.migrate(executor.loader.graph.leaf_nodes())

    collection = Collection.objects.get()
    assert collection.name == "Movies"
    assert list(collection.items.values_list("title", flat=True)) == ["In"]
    assert ApplicationSettings.load().active_collection_id == collection.id
