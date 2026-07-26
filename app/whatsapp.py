from urllib.parse import quote
from urllib.request import Request, urlopen
import json
import re

from app.config import get_settings


def normalize_phone(phone: str) -> str:
    cleaned = re.sub(r"[^\d+]", "", phone or "")
    if cleaned.startswith("+"):
        return cleaned[1:]
    if cleaned.startswith("00"):
        return cleaned[2:]
    return cleaned

def whatsapp_link(phone: str, message: str) -> str:
    number = normalize_phone(phone)
    return f"https://api.whatsapp.com/send/?phone={number}&text={quote(message)}" if number else ""

def whatsapp_enabled() -> bool:
    settings = get_settings()
    return bool(settings.whatsapp_token and settings.whatsapp_phone_number_id)


def send_whatsapp_message(phone: str, message: str) -> bool:
    settings = get_settings()
    number = normalize_phone(phone)
    if not number or not whatsapp_enabled():
        return False

    url = f"https://graph.facebook.com/v25.0/{settings.whatsapp_phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": number,
        "type": "text",
        "text": {"preview_url": True, "body": message},
    }
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.whatsapp_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        return 200 <= response.status < 300

def send_whatsapp_template(phone: str, template_name: str, language: str, params: list[str]) -> bool:
    settings = get_settings()
    number = normalize_phone(phone)
    if not number or not whatsapp_enabled():
        return False

    url = f"https://graph.facebook.com/v25.0/{settings.whatsapp_phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": str(p)} for p in params],
                }
            ] if params else [],
        },
    }
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.whatsapp_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        return 200 <= response.status < 300


def send_affectation_notification(phone: str, reference: str, atelier: str, priorite: str, sla_date: str) -> bool:
    return send_whatsapp_template(
        phone=phone,
        template_name="assignation_declaration",
        language="fr",
        params=[reference, atelier, priorite, sla_date],
    )