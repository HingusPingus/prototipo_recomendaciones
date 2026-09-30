"""Precondiciones de la lectura (T055): se evalúan **antes** de toda precedencia de estados.

La falta de declaración de gustos en el módulo es una precondición incumplida (FR-088): no produce un
sexto `result_type` —los estados siguen siendo cinco (DEP-6)— y se resuelve con `filters:{user}` y sus
`declared_modules`, sin consultar Postgres en el camino normal (RD-96, INV-1).
"""

from __future__ import annotations

import uuid

from recomendaciones.shared.domain import Module
from recomendaciones.shared.errors import DeclarationRequired, StaleAgeScale, UnknownUser
from recomendaciones.storage.cache.filters import FiltersCache, UserFilters


def check_preconditions(
    filters_cache: FiltersCache,
    user_id: uuid.UUID,
    module: Module,
    age_compatible_versions: frozenset[str],
) -> UserFilters:
    """Filtros del usuario listos para las guardas, o el error de precondición que corresponda.

    Usuario desconocido ⟹ 404. Escala etaria incompatible ⟹ se repuebla y, si persiste, 503 (DI-23); ese 503 se
    cuenta en `reco_unavailable_responses_total`; el recuento de usuarios con escala incompatible es del refresco
    etario (§7.5.1), no de la API.
    Módulo sin declaración ⟹ 412 (FR-088).
    """
    filters = filters_cache.get(user_id)
    if filters is None:
        raise UnknownUser()
    if filters.age_config_version not in age_compatible_versions:
        filters = filters_cache.repopulate(user_id)  # la entrada de caché era de otra escala
        if filters is None:
            raise UnknownUser()
        if filters.age_config_version not in age_compatible_versions:
            raise StaleAgeScale()  # nunca servir con un ordinal incomparable
    if Module(module) not in filters.declared_modules:
        raise DeclarationRequired("el usuario no declaró sus gustos en este módulo: debe declararlos antes de pedir recomendaciones")
    return filters
