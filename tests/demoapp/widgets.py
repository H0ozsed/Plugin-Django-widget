"""Widgets registered in the default registry for the test suite."""

from widget_hub import Service, Widget, params, register

demo = Service("demo", description="Test widgets")


@register
class Echo(Widget):
    """Returns its parameters, so tests can observe what reached fetch()."""

    service = demo
    name = "echo"
    description = "Echo the parameters back"
    params = [params.String("text", max_length=50), params.Integer("times", default=1)]

    def fetch(self, params, context):
        return {"text": params["text"] * params["times"]}


vault = Service("vault", description="Widgets using a stored secret")


@register
class Whoami(Widget):
    """Reports whether a credential reached fetch() (and its length, never its value)."""

    service = vault
    name = "whoami"
    params = [params.String("label", default="me")]
    cache_per_owner = True
    uses_credential = True

    def fetch(self, params, context):
        secret = context.credential
        return {"has_secret": secret is not None, "length": len(secret or "")}
