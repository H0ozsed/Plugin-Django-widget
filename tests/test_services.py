import pytest

from widget_hub import services
from widget_hub.exceptions import InvalidInput, NotFound, ParamValidationError
from widget_hub.models import WidgetInstance

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice(django_user_model):
    return django_user_model.objects.create_user("alice")


@pytest.fixture
def bob(django_user_model):
    return django_user_model.objects.create_user("bob")


def create(owner, **kwargs):
    payload = {"service": "demo", "widget": "echo", "params": {"text": "ab"}}
    payload.update(kwargs)
    return services.create_instance(owner, **payload)


def test_create_applies_defaults(alice):
    instance = create(alice)
    assert instance.owner == alice
    assert instance.params == {"text": "ab", "times": 1}
    assert instance.refresh_rate == 300
    assert instance.position == {}


def test_create_reports_every_invalid_field(alice):
    with pytest.raises(InvalidInput) as info:
        create(alice, params={"times": "x"}, refresh_rate=0, position={"x": -1})
    assert info.value.errors == {
        "params": {"text": "This parameter is required.", "times": "Expected an integer."},
        "refresh_rate": "Must be a positive integer (seconds).",
        "position": "x must be between 0 and 1000.",
    }
    assert WidgetInstance.objects.count() == 0


def test_create_unknown_widget(alice):
    with pytest.raises(InvalidInput) as info:
        create(alice, widget="nope")
    assert info.value.errors == {"widget": "Unknown widget demo.nope."}


@pytest.mark.parametrize(
    ("position", "message"),
    [
        ([], "Must be an object with keys x, y, w, h."),
        ({"z": 1}, "Unknown keys: z."),
        ({"w": True}, "w must be an integer."),
        ({"w": 0}, "w must be between 1 and 1000."),
    ],
)
def test_position_validation(alice, position, message):
    with pytest.raises(InvalidInput) as info:
        create(alice, position=position)
    assert info.value.errors == {"position": message}


def test_list_is_scoped_to_owner(alice, bob):
    mine = create(alice)
    create(bob)
    assert list(services.list_instances(alice)) == [mine]


@pytest.mark.parametrize(
    "action",
    [
        lambda owner, pk: services.get_instance(owner, pk),
        lambda owner, pk: services.update_instance(owner, pk, refresh_rate=10),
        lambda owner, pk: services.delete_instance(owner, pk),
        lambda owner, pk: services.fetch_instance_data(owner, pk),
    ],
)
def test_other_users_instances_are_not_found(alice, bob, action):
    theirs = create(bob)
    with pytest.raises(NotFound, match="Widget instance not found"):
        action(alice, theirs.pk)
    theirs.refresh_from_db()
    assert theirs.refresh_rate == 300


@pytest.mark.parametrize("pk", [999, "abc", None])
def test_missing_or_malformed_id(alice, pk):
    with pytest.raises(NotFound):
        services.get_instance(alice, pk)


def test_partial_update(alice):
    instance = create(alice, position={"x": 1})
    services.update_instance(alice, instance.pk, position={"x": 2, "y": 3})
    instance.refresh_from_db()
    assert instance.position == {"x": 2, "y": 3}
    assert instance.params == {"text": "ab", "times": 1}


def test_update_validates_params(alice):
    instance = create(alice)
    with pytest.raises(InvalidInput) as info:
        services.update_instance(alice, instance.pk, params={"text": "a" * 51})
    assert info.value.errors == {"params": {"text": "Must be at most 50 characters long."}}


def test_update_without_fields_is_a_no_op(alice):
    instance = create(alice)
    assert services.update_instance(alice, instance.pk) == instance


def test_delete(alice):
    instance = create(alice)
    services.delete_instance(alice, instance.pk)
    assert not WidgetInstance.objects.exists()


def test_fetch_passes_validated_params_and_context(alice):
    instance = create(alice, params={"text": "ab", "times": 2})
    assert services.fetch_instance_data(alice, instance.pk) == {"text": "abab"}


def test_fetch_revalidates_stored_params(alice):
    instance = create(alice)
    WidgetInstance.objects.filter(pk=instance.pk).update(params={"text": "x" * 99})
    with pytest.raises(ParamValidationError):
        services.fetch_instance_data(alice, instance.pk)


def test_fetch_for_unregistered_widget(alice):
    instance = create(alice)
    WidgetInstance.objects.filter(pk=instance.pk).update(widget="removed")
    with pytest.raises(NotFound, match=r"Unknown widget demo\.removed"):
        services.fetch_instance_data(alice, instance.pk)


def test_serialize(alice):
    data = services.serialize_instance(create(alice))
    assert data["service"] == "demo" and data["widget"] == "echo"
    assert set(data) == {
        "id",
        "service",
        "widget",
        "params",
        "refresh_rate",
        "position",
        "created_at",
        "updated_at",
    }
