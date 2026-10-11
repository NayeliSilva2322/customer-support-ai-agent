# Instrucciones para agentes

## Estructura y responsabilidades

- `backend/app.py` es el punto de entrada HTTP; conserva `app:app` para Uvicorn
  y Gunicorn.
- `backend/core/` contiene la orquestación, la persistencia de conversaciones
  y la observabilidad.
- `backend/agents/` contiene el triaje y la planificación.
- `backend/services/` contiene las capacidades e integraciones reutilizables.
- `backend/data/` contiene la base de conocimiento, datos simulados y datos
  locales de ejecución. No reemplaces ni borres datos persistidos al refactorizar.
- `frontend/` es la interfaz Streamlit. Mantén su comunicación con la API a
  través de `API_ROOT`.

## Reglas para cambios

- Usa imports de paquete (`core.*`, `agents.*`, `services.*`) para el código del
  backend; actualiza pruebas y mocks al cambiar rutas.
- Conserva las rutas de datos relativas a `backend/`, no al directorio del
  módulo, para que los cambios de paquetes no alteren almacenamiento ni fixtures.
- No agregues credenciales a archivos versionados. `.env` es local; cambia
  `.env.example` solo para documentar variables nuevas con valores vacíos o
  seguros.
- No afirmes que los diagnósticos simulados verifican hardware real.
- Mantén cada cambio acotado, haz explícitos los errores y no cambies contratos
  HTTP sin actualizar la documentación y sus pruebas.

## Validación

Desde la raíz del proyecto, ejecuta las pruebas del backend:

```powershell
Push-Location backend
python -m unittest discover -s tests -v
Pop-Location
```

Si modificas el arranque, la configuración de servicios o los contenedores,
valida también los comandos locales y Docker Compose documentados en `README.md`.
