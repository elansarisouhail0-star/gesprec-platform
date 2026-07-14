from io import BytesIO
from urllib.parse import quote

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from app.config import get_settings

router = APIRouter(prefix="/qr", tags=["qr"])

def public_url(request: Request) -> str:
    configured = get_settings().public_base_url
    if configured:
        return configured
    return str(request.base_url).rstrip("/")


def declaration_url(request: Request) -> str:
    return f"{public_url(request)}/?declaration=1"


def atelier_url(request: Request, atelier: str) -> str:
    return f"{public_url(request)}/?atelier={quote(atelier)}"


@router.get("/ateliers", response_class=HTMLResponse)
def qr_page(request: Request) -> str:
    img = "/qr/declaration.svg"
    return f"""
    <!doctype html>
    <html lang="fr">
    <head>
      <meta charset="utf-8">
      <title>QR Déclaration - Gesprec</title>
      <style>
        body{{font-family:Arial,sans-serif;background:#f4f6f8;color:#17202a;margin:24px;}}
        h1{{margin-bottom:18px;}}
        .card{{max-width:420px;background:white;border:1px solid #d8dee4;border-radius:8px;padding:22px;text-align:center;}}
        img{{width:220px;height:220px;}}
        p{{font-size:12px;word-break:break-all;color:#52616f;}}
        @media print{{button{{display:none;}} body{{background:white;}}}}
      </style>
    </head>
    <body>
      <button onclick="window.print()">Imprimer</button>
      <h1>QR code de création de déclaration</h1>
      <section class="card">
        <h2>Nouvelle déclaration</h2>
        <img src="{img}" alt="QR nouvelle déclaration">
        <p>{declaration_url(request)}</p>
        <p>Après le scan, le déclarant sélectionne l'atelier ciblé.</p>
      </section>
    </body>
    </html>
    """


@router.get("/declaration.svg")
def qr_declaration_svg(request: Request) -> Response:
    factory = qrcode.image.svg.SvgImage
    img = qrcode.make(declaration_url(request), image_factory=factory)
    out = BytesIO()
    img.save(out)
    return Response(content=out.getvalue(), media_type="image/svg+xml")


@router.get("/atelier.svg")
def qr_svg(request: Request, name: str) -> Response:
    factory = qrcode.image.svg.SvgImage
    img = qrcode.make(atelier_url(request, name), image_factory=factory)
    out = BytesIO()
    img.save(out)
    return Response(content=out.getvalue(), media_type="image/svg+xml")
