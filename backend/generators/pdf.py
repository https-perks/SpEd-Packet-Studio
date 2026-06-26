from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PdfRenderRequest:
    html: str
    base_url: str | None = None


def render_pdf(request: PdfRenderRequest) -> bytes:
    try:
        from weasyprint import HTML
    except OSError as reason:
        raise RuntimeError(
            "WeasyPrint is installed, but its native rendering libraries are unavailable. "
            "Install the WeasyPrint Windows GTK/Pango dependencies, then retry export."
        ) from reason
    return HTML(string=request.html, base_url=request.base_url).write_pdf()


def renderer_available() -> bool:
    try:
        from weasyprint import HTML  # noqa: F401
    except OSError:
        return False
    return True
