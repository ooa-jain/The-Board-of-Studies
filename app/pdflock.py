"""PDFium, the library that reads and draws PDFs here, is not safe to use
from two threads at once: a page asking for five thumbnails together could
bring the whole server down. Every use of it goes through this one lock."""

import threading

PDF_LOCK = threading.RLock()
