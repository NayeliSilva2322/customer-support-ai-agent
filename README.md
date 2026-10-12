# Agente de soporte técnico multimodal

Aplicación de demostración para analizar consultas de soporte técnico con texto
y una imagen opcional. Una interfaz Streamlit se comunica con una API FastAPI;
el backend reúne contexto, ejecuta un flujo de triaje y diagnóstico, propone
un plan y genera la respuesta con Google Gemini. Las conversaciones se guardan
en SQLite y el pipeline se puede instrumentar con Langfuse.


## Tabla de contenidos

- [Características](#características)
- [Arquitectura](#arquitectura)
- [Inicio rápido con Docker](#inicio-rápido-con-docker)
- [Requisitos](#requisitos)
- [Configuración](#configuración)
- [Ejecución con Docker Compose](#ejecución-con-docker-compose)
- [Ejecución local sin Docker](#ejecución-local-sin-docker)
- [Uso de la aplicación](#uso-de-la-aplicación)
- [Flujo de una conversación](#flujo-de-una-conversación)
- [Persistencia de datos](#persistencia-de-datos)
- [Observabilidad con Langfuse](#observabilidad-con-langfuse)
- [API HTTP](#api-http)
- [Pruebas](#pruebas)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Seguridad y limitaciones conocidas](#seguridad-y-limitaciones-conocidas)
- [Solución de problemas](#solución-de-problemas)
- [Licencia](#licencia)

## Características

- Interfaz de usuario construida con Streamlit.
- API HTTP construida con FastAPI.
- Análisis de consultas y generación de planes/respuestas con Gemini.
- Entrada multimodal: texto y una imagen PNG o JPEG opcional.
- Recuperación de una base de conocimiento local y de registros previos.
- Diagnósticos de ejemplo para hardware, memoria, controladores y registros.
- Registro de opiniones, soluciones fallidas y solicitudes de atención humana.
- Historial persistente de conversaciones y turnos en SQLite.
- Instrumentación opcional con Langfuse, agrupada por `session_id`.
- Ejecución en contenedores con Docker Compose y volúmenes persistentes.

Las comprobaciones de energía y controladores pueden producir resultados
simulados o aleatorios; no son una evaluación real del hardware.

## Arquitectura

```text
Navegador
   │
   ▼
Streamlit (frontend, puerto 8501)
   │ HTTP
   ▼
FastAPI (backend, puerto 8000)
   ├── Pipeline multimodal
   │    ├── Contexto externo o datos simulados
   │    ├── Base de conocimiento (RAG de ejemplo)
   │    ├── Memoria a largo plazo (LTM)
   │    ├── Triaje y diagnósticos
   │    ├── Plan de solución
   │    └── Generación de texto con Gemini
   ├── SQLite: conversaciones y turnos
   └── Langfuse: trazas y spans (opcional)
```

El frontend solicita una sesión al backend y conserva su `session_id` en el
estado de Streamlit. Ese identificador se utiliza para asociar los análisis y
turnos con una conversación. El backend puede volver a cargar la sesión desde
SQLite si la petición llega a otro worker.

## Inicio rápido con Docker

Requisitos: Docker Desktop (o Docker Engine) con Docker Compose v2 y una clave
de Google Gemini.

```powershell
Copy-Item .env.example .env
```

Edita `.env`, establece `GEMINI_API_KEY` y luego inicia la aplicación:

```powershell
docker compose up --build
```

- Interfaz: <http://localhost:8501>
- API: disponible dentro de la red privada de Compose. Para abrir su
  documentación desde el host, sigue el perfil de desarrollo en
  [Ejecución con Docker Compose](#ejecución-con-docker-compose).

Para detener los servicios, usa `Ctrl+C` y después `docker compose down`. Esto
conserva los volúmenes con datos persistentes.

## Requisitos

### Docker Compose

- Docker Desktop con Docker Compose v2.
- Una clave de Google Gemini para generar planes y respuestas.
- Opcionalmente, credenciales de Langfuse para observabilidad.

Las imágenes de backend y frontend utilizan Python 3.11.

### Para ejecución local sin Docker

- Python 3.11 recomendado.
- Dependencias del backend y frontend indicadas en sus respectivos
  `requirements.txt`.
- Acceso a Gemini y, para la generación de respuestas, `GEMINI_API_KEY`.

La instalación local de las dependencias de visión y machine learning puede
requerir memoria, configuración o ajustes específicos de plataforma. Docker
Compose es la opción recomendada para probar el proyecto.

## Configuración

La plantilla `.env.example` contiene nombres de variables y valores seguros;
no contiene credenciales funcionales. El archivo `.env` de la raíz lo utiliza
Docker Compose. Para ejecutar el backend localmente, crea además
`backend/.env`, que es el archivo leído por sus módulos.

1. Crea los archivos de entorno:

   ```powershell
   Copy-Item .env.example .env
   Copy-Item .env.example backend\.env
   ```

2. Edita el archivo que corresponda al modo de ejecución y define
   `GEMINI_API_KEY`. Configura las claves de Langfuse solo si deseas enviar
   trazas.

No agregues claves reales a Git. Tanto `.env` como `backend/.env` deben
mantenerse locales.

### Variables de entorno

| Variable | Obligatoria | Descripción |
| --- | --- | --- |
| `GEMINI_API_KEY` | Sí para generar texto | Clave de Google Gemini. Sin ella, el pipeline de respuesta devuelve un error. |
| `GEMINI_MODEL` | No | Modelo utilizado para generar texto. Predeterminado: `gemini-2.5-flash`. |
| `HUGGINGFACEHUB_API_TOKEN` | No | Variable prevista para Hugging Face; no es necesaria para iniciar la API o el frontend. |
| `LANGFUSE_PUBLIC_KEY` | No | Clave pública del proyecto Langfuse. |
| `LANGFUSE_SECRET_KEY` | No | Clave secreta del proyecto Langfuse. |
| `LANGFUSE_HOST` | No | URL de Langfuse. Predeterminado del SDK: `https://cloud.langfuse.com`. |
| `LANGFUSE_CAPTURE_CONTENT` | No | Si vale `true`, `1`, `yes` u `on`, permite capturar prompts y ciertas respuestas en Langfuse. Predeterminado: desactivado. |
| `FRONTEND_PORT` | No | Puerto publicado para Streamlit. Predeterminado: `8501`. |
| `API_ROOT` | No | URL base que usa el frontend para comunicarse con FastAPI. En Docker Compose se establece como `http://backend:8000`. |

Langfuse se activa únicamente cuando están configuradas **ambas** claves,
`LANGFUSE_PUBLIC_KEY` y `LANGFUSE_SECRET_KEY`. Si faltan, la aplicación sigue
funcionando sin enviar trazas. `API_ROOT` se establece automáticamente para el
frontend en Docker; en ejecución local, configúralo en la terminal del
frontend.

## Ejecución con Docker Compose

Desde la raíz del repositorio, después de configurar `.env`:

```powershell
docker compose up --build
```

La configuración principal inicia los dos servicios:

- Frontend Streamlit: <http://localhost:8501>
- API FastAPI: accesible desde el frontend como `http://backend:8000`.
- La API no publica un puerto en el host en el perfil normal.

Para desarrollo, publica la API en el host y monta el código del backend para
que los cambios se apliquen sin reconstruir su imagen:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Con este perfil, abre la documentación interactiva de la API en
<http://localhost:8000/docs>. El frontend sigue disponible en
<http://localhost:8501>.

Detén los servicios con `Ctrl+C` o apágalos desde otra terminal:

```powershell
docker compose down
```

Los volúmenes `ltm_data` y `hf_cache` se conservan al detener los servicios.
`docker compose down -v` también elimina esos volúmenes y, por tanto, sus datos;
úsalo solo si quieres borrar intencionalmente el historial y la caché.

## Ejecución local sin Docker

Instala por separado las dependencias del backend y del frontend en el mismo
entorno virtual. La configuración local de Python está pensada para Python
3.11.

### Windows (PowerShell)

Desde la raíz del proyecto:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instala las dependencias de ambos componentes:

```powershell
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
python -m pip install -r frontend\requirements.txt
```

En la primera terminal, inicia la API:

```powershell
Set-Location backend
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

Abre una segunda terminal en la raíz del proyecto, activa el entorno virtual e
inicia Streamlit:

```powershell
.\.venv\Scripts\Activate.ps1
Set-Location frontend
$env:API_ROOT = "http://127.0.0.1:8000"
python -m streamlit run streamlit_app.py
```

Activa el entorno virtual antes de cambiar al directorio de cada servicio.

### macOS y Linux (bash)

Desde la raíz del proyecto:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
python -m pip install -r frontend/requirements.txt
```

En la primera terminal, inicia la API:

```bash
source .venv/bin/activate
cd backend
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

En otra terminal desde la raíz del proyecto, inicia Streamlit:

```bash
source .venv/bin/activate
cd frontend
export API_ROOT="http://127.0.0.1:8000"
python -m streamlit run streamlit_app.py
```

Abre <http://localhost:8501>. La API estará disponible en
<http://127.0.0.1:8000/docs>.

## Uso de la aplicación

1. Abre Streamlit y escribe el ID de usuario.
2. Escribe una descripción del problema y, si corresponde, adjunta una imagen
   PNG o JPEG.
3. Pulsa **Iniciar sesión**. El backend devuelve un UUID para la conversación.
4. Pulsa **Analizar**. El resultado incluye la respuesta, el triaje, el plan,
   las comprobaciones y si hace falta escalar el caso.
5. Usa los paneles de memoria para consultar opiniones o solicitudes de
   atención asociadas a la sesión.
6. Envía una opinión mediante el control de calificación y el campo de texto.
7. En **Conversaciones por ID**, consulta la tabla del usuario y selecciona una
   conversación para desplegar sus turnos.

La tabla de conversaciones muestra hasta 100 sesiones del usuario ordenadas
por fecha de actualización. La API admite un máximo de 500 registros por
solicitud.

## Flujo de una conversación

Para cada llamada a `POST /analyze`, el pipeline:

1. Valida y recupera el estado de la sesión usando `session_id`.
2. Obtiene la configuración del usuario y sus registros recientes. En el
   entorno actual se consulta una URL de ejemplo y se recurre a los archivos
   locales de datos simulados cuando la consulta no está disponible.
3. Recupera contenido de la base de conocimiento y posibles registros previos.
4. Clasifica la consulta con el nodo de triaje.
5. Ejecuta comprobaciones de diagnóstico y determina un estado global.
6. Guarda una solución fallida o crea una solicitud de atención cuando aplica.
7. Genera un plan de solución y, después, la respuesta de Gemini.
8. Si se recibió una opinión, la guarda; una calificación baja también puede
   activar una estrategia de replanteamiento.
9. Persiste el turno en SQLite y devuelve los resultados al frontend.

Si se adjunta una imagen, el backend intenta obtener una descripción con
BLIP-2. El archivo temporal se utiliza durante el procesamiento; no forma parte
del registro de turnos.

## Persistencia de datos

La aplicación utiliza dos almacenamientos locales con propósitos diferentes:

### Conversaciones y turnos

`backend/core/conversation_store.py` mantiene la base
`backend/data/ltm/conversations.sqlite3` (en Docker se encuentra en
`/app/data/ltm/conversations.sqlite3`).

- `conversations`: una fila por `session_id`, con usuario, fechas, cantidad de
  turnos y resumen del último turno.
- `conversation_turns`: mensajes de usuario y asistente, estado y fecha de cada
  turno, relacionados por `session_id`.

En Docker, estos datos quedan dentro del volumen `ltm_data`. En el entorno
local, la ruta de la base de datos está cubierta por `.gitignore`.

### Memoria a largo plazo

`backend/services/ltm_module.py` almacena soluciones fallidas, opiniones y
solicitudes de atención en
`backend/data/ltm/sample_failed_solutions.json`. El mismo volumen `ltm_data` la
conserva en Docker. Los archivos locales SQLite y JSON de este directorio se
excluyen de Git para evitar subir conversaciones o memoria de usuario.

## Observabilidad con Langfuse

El pipeline crea una traza por cada análisis. Las trazas de una conversación
comparten `session_id`, lo que permite agrupar consultas sucesivas en Langfuse.
El usuario de Langfuse se asocia con el `user_id`.

La traza contiene spans para operaciones como:

- `context.fetch_user_data`
- `context.retrieve_knowledge`
- `triage.classify`
- `diagnostics.run`
- `memory.store_failed_solution`
- `handoff.store`
- `planner.create_plan`
- `response.generate`
- `feedback.store`
- `planner.replan` cuando corresponde

### Activación

Agrega las credenciales de tu proyecto Langfuse al archivo `.env`:

```dotenv
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_CAPTURE_CONTENT=false
```

Para una instalación propia, sustituye `LANGFUSE_HOST` por la URL de tu
instancia. Reinicia los servicios después de modificar las variables:

```powershell
docker compose up --build
```

### Captura y privacidad del contenido

Por defecto, la instrumentación registra metadatos operativos —como longitudes,
conteos, decisiones y estados— sin enviar el texto de la consulta ni el prompt
completo a Langfuse.

Si tu política de datos lo permite y necesitas inspeccionar prompts y
respuestas:

```dotenv
LANGFUSE_CAPTURE_CONTENT=true
```

Al activar esta opción, contenido de usuario puede enviarse a Langfuse. Revisa
los requisitos de consentimiento, retención y acceso de tu organización antes
de habilitarla. El SDK vacía las trazas pendientes durante el apagado normal
del backend.

Langfuse y el historial SQLite son complementarios: Langfuse sirve para
inspeccionar la ejecución técnica del pipeline, mientras SQLite alimenta la
tabla de conversaciones y el detalle de sus turnos en la interfaz.

## API HTTP

FastAPI expone documentación OpenAPI interactiva en `/docs` y el esquema JSON
en `/openapi.json`.

### Sesiones y conversaciones

| Método | Ruta | Propósito |
| --- | --- | --- |
| `POST` | `/start_session` | Crea una sesión y devuelve su `session_id`. |
| `POST` | `/analyze` | Procesa texto y una imagen opcional; requiere `session_id`. |
| `GET` | `/conversations?user_id=...&limit=100` | Lista las conversaciones del usuario. `limit` debe estar entre 1 y 500. |
| `GET` | `/conversations/{session_id}?user_id=...` | Devuelve la conversación y todos sus turnos, validando la coincidencia de usuario. |

Ejemplo para iniciar una sesión:

```powershell
curl.exe -X POST "http://localhost:8000/start_session" `
  -H "Content-Type: application/json" `
  -d '{"user_id":"usuario-demo","initial_text":"Mi equipo no enciende"}'
```

La respuesta incluye un identificador similar a:

```json
{
  "session_id": "8af7c3d4-...",
  "created_at": "2026-10-10T12:00:00Z"
}
```

Ejemplo para consultar conversaciones:

```powershell
curl.exe "http://localhost:8000/conversations?user_id=usuario-demo&limit=100"
```

Ejemplo para enviar una consulta de texto al análisis:

```powershell
curl.exe -X POST "http://localhost:8000/analyze" `
  -F "session_id=8af7c3d4-..." `
  -F "text=Mi equipo no enciende"
```

Para enviar una imagen, agrega un campo multipart, por ejemplo
`-F "file=@C:\ruta\equipo.jpg"`.

### Diagnóstico y memoria

| Método | Ruta | Propósito |
| --- | --- | --- |
| `POST` | `/run_diagnostics` | Ejecuta el conjunto de comprobaciones usando `user_id` o `session_id`. |
| `POST` | `/store_failed_solution` | Guarda una solución fallida; requiere `session_id`, `text` y `solution_summary`. |
| `POST` | `/query_ltm` | Busca coincidencias de texto en la memoria a largo plazo. |
| `POST` | `/ltm_query?q=...` | Alternativa de consulta LTM mediante parámetro. |
| `POST` | `/summarize_ltm_activity` | Resume registros de memoria, opcionalmente filtrados por `session_id`. |
| `POST` | `/store_feedback` | Guarda una opinión asociada a una sesión. |
| `POST` | `/submit_feedback` | Alias de `/store_feedback`, utilizado por la interfaz. |
| `POST` | `/query_feedback` | Busca opiniones por sesión, usuario o texto. |
| `POST` | `/store_handoff` | Registra una solicitud de atención humana. |
| `POST` | `/query_handoffs` | Busca solicitudes de atención humana, opcionalmente por sesión. |

Los endpoints de memoria reciben y devuelven JSON. Consulta `/docs` para ver
los campos exactos y ejemplos de los modelos de petición.

## Pruebas

La suite usa `unittest` y verifica persistencia y aislamiento de conversaciones,
el procesamiento de una sesión desde otro worker y las rutas de datos del
backend.

Desde la raíz del proyecto:

```powershell
Push-Location backend
python -m unittest discover -s tests -v
Pop-Location
```

## Estructura del proyecto

```text
.
├── AGENTS.md                    # Reglas del agente para cambios seguros y pruebas
├── .env.example                 # Plantilla segura de configuración
├── .gitignore
├── backend/
│   ├── app.py                    # Punto de entrada de la API FastAPI
│   ├── agents/                   # Triaje y planificación
│   ├── core/                     # Pipeline, persistencia y observabilidad
│   ├── services/                 # Memoria, RAG, modelos y herramientas
│   ├── data/
│   │   ├── knowledge_base/       # Base de conocimiento de ejemplo
│   │   ├── ltm/                  # Memoria y base SQLite locales (ignoradas por Git)
│   │   └── mock_external/        # Respuestas de servicios simulados
│   ├── tests/                    # Pruebas unitarias
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── streamlit_app.py          # Interfaz Streamlit
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml            # Configuración base de servicios y volúmenes
├── docker-compose.dev.yml        # Publicación y montaje para desarrollo
└── README.md
```

Los puntos de entrada siguen siendo `backend/app.py` para FastAPI y
`frontend/streamlit_app.py` para Streamlit; la estructura interna del backend
se organiza por responsabilidad sin cambiar los comandos de Docker Compose.
Los entornos virtuales, los archivos `.env` y los datos locales de memoria no
deben subirse al repositorio.

## Seguridad y limitaciones conocidas

- La API no implementa autenticación ni autorización. `user_id` funciona como
  filtro de datos, no como prueba de identidad; no expongas el servicio a
  Internet ni lo uses con datos sensibles sin añadir autenticación y controles
  de acceso adecuados.
- CORS permite todos los orígenes en la configuración actual.
- SQLite guarda el texto de entrada y la respuesta; la memoria LTM también
  conserva soluciones fallidas, opiniones y solicitudes de atención. Protege
  los volúmenes y los respaldos de acuerdo con tu política de privacidad.
- Mantén `LANGFUSE_CAPTURE_CONTENT=false` salvo que sea necesario capturar
  contenido y esté aprobado.
- La integración con `api.example.com`, la base de conocimiento de ejemplo y
  varios diagnósticos son demostrativos. Sustitúyelos por fuentes reales antes
  de un despliegue productivo.
- El modelo BLIP-2 se descarga y carga al procesar imágenes; su disponibilidad,
  consumo de memoria y compatibilidad dependen del entorno. Si no puede
  cargarse, el análisis de la imagen devuelve un error.
- El uso de SQLite es apropiado para esta aplicación de demostración y
  despliegues pequeños. Evalúa una base de datos de servidor si necesitas alta
  concurrencia, réplicas o escalado horizontal.

## Solución de problemas

### El backend no puede generar respuestas

Verifica que `GEMINI_API_KEY` esté definido en `.env` para Docker o en
`backend/.env` para ejecución local. Reinicia el backend después de cambiarlo.

### Langfuse no muestra trazas

Confirma que `LANGFUSE_PUBLIC_KEY` y `LANGFUSE_SECRET_KEY` estén presentes, que
`LANGFUSE_HOST` apunte a tu instancia y que el contenedor se haya reiniciado.
Las trazas se vacían durante el apagado normal; una terminación abrupta puede
impedir el envío de los últimos eventos.

### No aparece una conversación en la tabla

La tabla está filtrada por el `user_id` escrito en la interfaz. Usa el mismo
identificador con el que se inició la sesión. Comprueba también que el volumen
`ltm_data` esté disponible y que el backend pueda escribir en
`/app/data/ltm`.

### El frontend no se conecta a la API

En Docker, el frontend debe usar `API_ROOT=http://backend:8000`. En ejecución
local, utiliza `http://127.0.0.1:8000`. Comprueba el estado del servicio backend
y abre `/docs` para verificar que la API arrancó.

### La API devuelve un error al analizar una imagen

El procesamiento requiere que BLIP-2 y sus dependencias estén disponibles y
que el modelo pueda cargarse en el entorno. Prueba primero el flujo de texto
sin imagen para verificar el resto del pipeline.
