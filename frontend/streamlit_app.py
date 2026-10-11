import os

import requests
import streamlit as st
from streamlit_agraph import Config, Edge, Node, agraph

st.set_page_config(page_title="Agente multimodal", layout="wide")
st.title("Agente de soporte multimodal")
API_ROOT = os.getenv("API_ROOT", "http://localhost:8000")

col1, col2 = st.columns([2, 1])
with col1:
    user_id = st.text_input("ID de usuario", "student")
    text = st.text_area("Descripción del problema")
with col2:
    uploaded = st.file_uploader(
        "Adjuntar imagen (opcional)",
        type=["png", "jpg", "jpeg"],
    )

if st.button("Iniciar sesión"):
    try:
        response = requests.post(
            f"{API_ROOT}/start_session",
            json={"user_id": user_id, "initial_text": text},
            timeout=10,
        )
        response.raise_for_status()
        st.session_state["session_id"] = response.json()["session_id"]
        st.success("Sesión iniciada.")
    except (requests.RequestException, ValueError, KeyError) as error:
        st.error(f"No se pudo iniciar la sesión: {error}")

session_id = st.session_state.get("session_id")
if session_id:
    st.markdown(f"### Sesión actual: `{session_id}`")
    if st.button("Analizar"):
        try:
            form_data = {"session_id": session_id, "text": text}
            files = (
                {
                    "file": (
                        uploaded.name,
                        uploaded.getvalue(),
                        uploaded.type or "application/octet-stream",
                    )
                }
                if uploaded is not None
                else None
            )
            response = requests.post(
                f"{API_ROOT}/analyze",
                data=form_data,
                files=files,
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()
            st.subheader("Resultado del análisis")
            st.json(result)

            if result.get("manual_handoff_required"):
                st.warning("El caso requiere atención humana y fue registrado.")
        except (requests.RequestException, ValueError, KeyError) as error:
            st.error(f"No se pudo completar el análisis: {error}")

    run_col1, run_col2 = st.columns([1, 1])
    with run_col1:
        st.subheader("Operaciones de memoria")
        if st.button("Consultar registros LTM"):
            try:
                response = requests.post(
                    f"{API_ROOT}/query_ltm",
                    json={"query_text": text or "diagnóstico"},
                    timeout=10,
                )
                response.raise_for_status()
                st.json(response.json())
            except (requests.RequestException, ValueError) as error:
                st.error(f"No se pudieron consultar los registros: {error}")

        if st.button("Ver opiniones"):
            try:
                response = requests.post(
                    f"{API_ROOT}/query_feedback",
                    json={"session_id": session_id, "user_id": user_id},
                    timeout=10,
                )
                response.raise_for_status()
                st.json(response.json())
            except (requests.RequestException, ValueError) as error:
                st.error(f"No se pudieron consultar las opiniones: {error}")

        if st.button("Ver solicitudes de atención"):
            try:
                response = requests.post(
                    f"{API_ROOT}/query_handoffs",
                    json={"session_id": session_id},
                    timeout=10,
                )
                response.raise_for_status()
                st.json(response.json())
            except (requests.RequestException, ValueError) as error:
                st.error(f"No se pudieron consultar las solicitudes: {error}")

    with run_col2:
        st.subheader("Flujo de atención")
        nodes = [
            Node(id="Input", label="Entrada", size=25),
            Node(id="Diagnostics", label="Diagnóstico", size=30),
            Node(id="Planner", label="Plan de solución", size=30),
            Node(id="Handoff", label="Atención humana", size=25),
            Node(id="Feedback", label="Opinión", size=25),
        ]
        edges = [
            Edge(source="Input", target="Diagnostics"),
            Edge(source="Diagnostics", target="Planner"),
            Edge(source="Planner", target="Handoff"),
            Edge(source="Handoff", target="Feedback"),
        ]
        agraph(
            nodes=nodes,
            edges=edges,
            config=Config(width=400, height=400, directed=True, physics=True),
        )

    st.subheader("Enviar opinión")
    feedback_text = st.text_area(
        "Escriba su opinión",
        placeholder="Comparta su experiencia o sugerencias.",
    )
    rating = st.slider("Califique su experiencia", 1, 5, 4)
    if st.button("Enviar opinión"):
        try:
            response = requests.post(
                f"{API_ROOT}/submit_feedback",
                json={
                    "session_id": session_id,
                    "user_id": user_id,
                    "feedback_text": feedback_text,
                    "rating": rating,
                },
                timeout=10,
            )
            response.raise_for_status()
            st.success("Opinión guardada.")
            st.json(response.json())
        except (requests.RequestException, ValueError) as error:
            st.error(f"No se pudo guardar la opinión: {error}")
else:
    st.info("Inicie una sesión para habilitar el análisis y la memoria.")

st.markdown("---")
st.subheader("Conversaciones por ID")
if user_id.strip():
    try:
        response = requests.get(
            f"{API_ROOT}/conversations",
            params={"user_id": user_id.strip(), "limit": 100},
            timeout=10,
        )
        response.raise_for_status()
        conversations = response.json()["conversations"]
        if conversations:
            st.dataframe(
                [
                    {
                        "ID de conversación": conversation["session_id"],
                        "Actualizada": conversation["updated_at"],
                        "Turnos": conversation["turn_count"],
                        "Estado": conversation["last_status"] or "Sin analizar",
                        "Último mensaje": conversation["last_user_message"][:160],
                    }
                    for conversation in conversations
                ],
                use_container_width=True,
            )
            session_ids = [
                conversation["session_id"] for conversation in conversations
            ]
            preferred_index = (
                session_ids.index(session_id)
                if session_id in session_ids
                else 0
            )
            selected_session_id = st.selectbox(
                "Ver turnos de la conversación",
                session_ids,
                index=preferred_index,
            )
            detail_response = requests.get(
                f"{API_ROOT}/conversations/{selected_session_id}",
                params={"user_id": user_id.strip()},
                timeout=10,
            )
            detail_response.raise_for_status()
            for turn in detail_response.json()["turns"]:
                with st.expander(
                    f"Turno {turn['turn_id']} · {turn['created_at']} · "
                    f"{turn['status']}"
                ):
                    st.markdown("**Usuario**")
                    st.text(turn["user_message"])
                    st.markdown("**Asistente**")
                    st.text(turn["assistant_message"])
        else:
            st.info("Este usuario todavía no tiene conversaciones guardadas.")
    except (requests.RequestException, ValueError, KeyError) as error:
        st.error(f"No se pudieron cargar las conversaciones: {error}")
else:
    st.info("Ingrese un ID de usuario para consultar sus conversaciones.")
