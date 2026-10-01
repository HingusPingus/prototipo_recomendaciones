"""Declara los gustos de los usuarios de fondo contra la API real (`reco-demo semilla`), como lo haría `api-general`.

Así el worker les calcula perfil y top-N, y el término colaborativo tiene vecinos cuando la persona de la demo
declara los suyos. Las personas de la demo (Ana, Tomás) no se declaran: eso se hace en vivo.
Reejecutable: una declaración que ya existe responde 409 y se da por buena.
"""

from __future__ import annotations

import sys

import httpx

from recomendaciones.demo import datos


def declarar_fondo(http: httpx.Client) -> int:
    """Devuelve la cantidad de declaraciones que fallaron."""
    fallas = 0
    for user in datos.usuarios():
        if user.perfil is None:
            continue
        for module, tags in datos.PERFILES[user.perfil].tags.items():
            response = http.post(f"/internal/v1/declarations/{user.id}", json={"module": module, "tags": list(tags)})
            if response.status_code not in (201, 409):
                fallas += 1
                print(f"{user.alias}/{module}: {response.status_code} {response.text}", file=sys.stderr)
    return fallas


def run(*, api_key: str, recomendaciones_url: str) -> int:
    with httpx.Client(base_url=recomendaciones_url, headers={"X-Internal-API-Key": api_key}, timeout=10) as http:
        fallas = declarar_fondo(http)
    print(f"declaraciones de fondo listas ({fallas} con error)")
    return 1 if fallas else 0
