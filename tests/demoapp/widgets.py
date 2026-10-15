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
