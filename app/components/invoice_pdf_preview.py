import time
from typing import Union

from nicegui import ui


class InvoicePdfPreview:
    def __init__(self, invoice_id: Union[int, str]) -> None:
        self.invoice_id = invoice_id
        self.rev = self._next_rev()

        with ui.column().classes("w-full gap-2"):
            self._open_button = ui.button("Open PDF").props(
                f"outline href='{self._pdf_url()}' target='_blank'"
            )
            self._iframe = ui.html(self._iframe_html(), sanitize=False).classes(
                "w-full"
            )

    def refresh(self) -> None:
        self.rev = self._next_rev()
        self._open_button.props(f"outline href='{self._pdf_url()}' target='_blank'")
        self._iframe.content = self._iframe_html()

    def _next_rev(self) -> int:
        return int(time.time() * 1000)

    def _viewer_url(self) -> str:
        return f"/viewer/invoice/{self.invoice_id}?rev={self.rev}"

    def _pdf_url(self) -> str:
        return f"/api/invoices/{self.invoice_id}/pdf?rev={self.rev}"

    def _iframe_html(self) -> str:
        return (
            f"<iframe src=\"{self._viewer_url()}\" "
            "style=\"width:100%; height:80vh; border:none;\"></iframe>"
        )
