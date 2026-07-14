ATELIERS = [
    "HITACHI Remise",
    "HITACHI VA",
    "DIESEL",
    "POSTE GASOIL",
    "MAGASIN DIESEL",
    "LABORATOIRE ÉLECTRONIQUE",
    "MAGASIN LOCAL",
    "TOUR EN FOSSE",
    "AJUSTAGE",
    "ANSALDO",
    "APPROVISIONNEMENT",
    "RH",
    "COORDINATION",
    "PRESTATAIRES MALOCO",
    "INSTALLATION ET OUTILLAGE",
]


def split_multi(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]
