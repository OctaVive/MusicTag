from django import template

register = template.Library()


@register.filter
def duration(value):
    seconds = int(value or 0)
    return f"{seconds // 60}:{seconds % 60:02}"


@register.simple_tag(takes_context=True)
def query(context, **kwargs):
    params = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = value
    return "?" + params.urlencode()
