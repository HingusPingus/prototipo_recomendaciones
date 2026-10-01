"""Modo demo (`reco-demo`): un `api-general` simulado y datos de ejemplo para mostrar el servicio de punta a punta
mientras la integración con el `api-general` real no está disponible.

No forma parte del camino de producción: ningún otro paquete lo importa, y los procesos reales (`reco-api`,
`reco-worker`, `reco-transformer`, `reco-batch`) corren sin cambios contra él. Se reemplaza por el real
apuntando `RECO_API_GENERAL_BASE_URL` a su URL.
"""
