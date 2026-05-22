from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def qs_replace(context, **kwargs):
    query = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value in {None, ""}:
            query.pop(key, None)
        else:
            query[key] = value
    return query.urlencode()


@register.simple_tag(takes_context=True)
def sort_link(context, field, default_dir="asc"):
    request = context["request"]
    current_sort = context.get("sort", request.GET.get("sort", "name"))
    current_dir = context.get("direction", request.GET.get("dir", "asc"))
    if current_sort == field:
        next_dir = "desc" if current_dir == "asc" else "asc"
    else:
        next_dir = default_dir
    query = request.GET.copy()
    query["sort"] = field
    query["dir"] = next_dir
    query.pop("page", None)
    return f"?{query.urlencode()}"


@register.simple_tag(takes_context=True)
def sort_indicator(context, field):
    current_sort = context.get("sort", context["request"].GET.get("sort", "name"))
    current_dir = context.get("direction", context["request"].GET.get("dir", "asc"))
    if current_sort != field:
        return ""
    return "▲" if current_dir == "asc" else "▼"
