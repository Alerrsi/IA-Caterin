# T11 — Despliegue en producción
- Estado: pendiente
- Depende de: T08
- Funcionalidad: transversal

## Objetivo
Tener Cáterin funcionando en internet con HTTPS, respaldos y un costo mensual conocido y bajo, para que una emprendedora lo use de verdad.

## Contexto y decisiones previas
- Dimensionamiento estimado y costo referencial: `docs/ARCHITECTURE.md`, sección 7 (**no verificado**).
- Seguridad de infraestructura: `docs/SECURITY.md`, sección 7.
- Supuesto: un solo VPS para el MVP; varias pymes comparten la instancia.

## Entregables
- [ ] Cotizar al menos 3 proveedores de VPS (4 a 8 vCPU, 16 GB) con precio, región y fecha; elegir uno y anotar el motivo.
- [ ] `infra/docker-compose.prod.yml`: Caddy (HTTPS automático, cabeceras de seguridad), API, web estática, Postgres y Ollama **sin puertos públicos**; reinicio automático; límites de memoria por servicio.
- [ ] Precarga de modelos (`ollama pull`) y verificación con `scripts/verify_models.py` en el arranque.
- [ ] Backups: `pg_dump` diario cifrado fuera del VPS, retención (p. ej. 7 diarios y 4 semanales), y **restauración probada** en una base limpia.
- [ ] Observabilidad básica: logs JSON con rotación, healthchecks, alerta simple si `/health/ready` falla (p. ej. un monitor gratuito de uptime).
- [ ] Repetir en el VPS las mediciones de latencia del asistente (niveles 0 a 2), del cotizador y de la visión; actualizar los presupuestos si no se cumplen (`AGENTS.md`, sección 3.1).
- [ ] `docs/DEPLOY.md`: paso a paso, rotación de secretos, actualización, restauración.
- [ ] Costo mensual real documentado en `docs/ARCHITECTURE.md`, sección 7.3, con fecha y fuente.

## Criterios de aceptación
- `https://<dominio>` sirve la PWA con un certificado válido; `/api/v1/health/ready` responde 200.
- Escaneo de puertos: solo 80 y 443 abiertos.
- Se borró una base de prueba y se restauró desde el backup, con el tiempo de restauración anotado.
- El costo mensual documentado incluye todos los ítems (VPS, dominio, backups) con su fuente.

## Pruebas requeridas
- Smoke test automatizado contra producción (login de demo, consulta de nivel 0, cotización de demo).
- Restauración de backup.

## Fuera de alcance
- Alta disponibilidad, varias réplicas, Kubernetes.

## Riesgos y preguntas abiertas
- Si las vCPU del VPS son lentas, los niveles 1 y 2 pueden no cumplir el presupuesto: opciones en `AGENTS.md`, sección 3.1 (ajustar presupuestos, GPU puntual o proveedor externo con datos minimizados y consentimiento).
- ¿Quién paga el VPS y el dominio durante el semestre?

## Resumen de cierre
(se completa al terminar)
