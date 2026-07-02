from io import BytesIO
from urllib.parse import quote

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from app.config import get_settings

router = APIRouter(prefix="/qr", tags=["qr"])

ATELIERS = ["Atelier HITACHI", "Atelier levage", "Atelier Tour en fosse"]


def public_url(request: Request) -> str:
    configured = get_settings().public_base_url
    if configured:
        return configured
    return str(request.base_url).rstrip("/")


def atelier_url(request: Request, atelier: str) -> str:
    return f"{public_url(request)}/?atelier={quote(atelier)}"


@router.get("/ateliers", response_class=HTMLResponse)
def qr_page(request: Request) -> str:
    cards = []
    for atelier in ATELIERS:
        img = f"/qr/atelier.svg?name={quote(atelier)}"
        cards.append(
            f"""
            <section class="card">
              <h2>{atelier}</h2>
              <img src="{img}" alt="QR {atelier}">
              <p>{atelier_url(request, atelier)}</p>
            </section>
            """
        )
    return f"""
    <!doctype html>
    <html lang="fr">
    <head>
      <meta charset="utf-8">
      <title>QR Ateliers - Gesprec</title>
      <style>
        body{{font-family:Arial,sans-serif;background:#f4f6f8;color:#17202a;margin:24px;}}
        h1{{margin-bottom:18px;}}
        .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px;}}
        .card{{background:white;border:1px solid #d8dee4;border-radius:8px;padding:18px;text-align:center;}}
        img{{width:220px;height:220px;}}
        p{{font-size:12px;word-break:break-all;color:#52616f;}}
        @media print{{button{{display:none;}} body{{background:white;}}}}
      </style>
    </head>
    <body>
      <button onclick="window.print()">Imprimer</button>
      <h1>QR codes des ateliers</h1>
      <div class="grid">{''.join(cards)}</div>
    </body>
    </html>
    """


@router.get("/atelier.svg")
def qr_svg(request: Request, name: str) -> Response:
    factory = qrcode.image.svg.SvgImage
    img = qrcode.make(atelier_url(request, name), image_factory=factory)
    out = BytesIO()
    img.save(out)
    return Response(content=out.getvalue(), media_type="image/svg+xml")
