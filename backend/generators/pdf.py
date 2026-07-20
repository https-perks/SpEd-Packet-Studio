from dataclasses import dataclass
import logging
from backend.native_runtime import configure_bundled_native_libraries

logging.getLogger("fontTools").setLevel(logging.WARNING)
logging.getLogger("weasyprint").setLevel(logging.ERROR)


@dataclass(frozen=True, slots=True)
class PdfRenderRequest:
    html: str
    base_url: str | None = None


def render_pdf(request: PdfRenderRequest) -> bytes:
    configure_bundled_native_libraries()
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
