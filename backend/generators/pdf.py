from dataclasses import dataclass
@dataclass(frozen=True, slots=True)
class PdfRenderRequest:
    html: str
    base_url: str | None = None
def render_pdf(_: PdfRenderRequest) -> bytes:
    """Reserve the WeasyPrint boundary without implementing packet generation."""
    # TODO(Sprint 3/4): Render deterministic packet HTML using WeasyPrint.
    raise NotImplementedError("PDF packet generation is outside Sprint 0.")
