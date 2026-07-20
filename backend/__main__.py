import multiprocessing
import base64
import sys

multiprocessing.freeze_support()

import uvicorn
from backend.native_runtime import configure_bundled_native_libraries, configure_frozen_stdio, start_parent_process_watchdog

configure_bundled_native_libraries()
configure_frozen_stdio()
start_parent_process_watchdog()

from backend.config import settings

def main() -> None:
    if "--self-test" in sys.argv:
        from backend.generators.pdf import PdfRenderRequest, render_pdf
        settings.paths.initialize()
        font = settings.paths.builtin_assets_dir / "fonts" / "SpEdPacketTest.ttf"
        if not font.is_file():
            raise RuntimeError(f"Packaged custom font is missing: {font}")
        imported_image = settings.paths.temp_dir / "sidecar-self-test.png"
        imported_image.write_bytes(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nWQAAAAASUVORK5CYII="
        ))
        html = f"""
        <style>
          @font-face {{ font-family: PacketTest; src: url('{font.as_uri()}'); }}
          body {{ font-family: PacketTest; }}
          .illustration {{ width: 120px; height: 40px; background: linear-gradient(135deg, #17345f, #2bb5c4); }}
        </style>
        <h1>SpEd Packet Studio</h1>
        <div class="illustration"></div>
        <svg width="120" height="40" xmlns="http://www.w3.org/2000/svg"><circle cx="20" cy="20" r="18" fill="#e56b2f"/></svg>
        <img src="{imported_image.as_uri()}" width="16" height="16">
        """
        result = render_pdf(PdfRenderRequest(html=html, base_url=str(settings.resource_dir)))
        if not result.startswith(b"%PDF"):
            raise RuntimeError("Packaged PDF renderer did not produce a PDF.")
        output = settings.cache_dir / "sidecar-self-test.pdf"
        output.write_bytes(result)
        print(f"backend sidecar self-test passed: {output}")
        return
    uvicorn.run("backend.main:app", host=settings.api_host, port=settings.api_port,
                reload=settings.environment == "development", access_log=settings.environment == "development")

if __name__ == "__main__":
    main()
