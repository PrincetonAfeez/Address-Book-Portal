"""Shared CSV streaming helper used by importers and exporters."""

class CsvEcho:
    """Writer target that returns each row as a string for StreamingHttpResponse."""

    def write(self, value):
        return value
