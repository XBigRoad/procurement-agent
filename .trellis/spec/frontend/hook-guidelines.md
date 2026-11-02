# Lifecycle

This Python interface has no React hooks. Streamlit reruns read a ReviewSession
from session_state. Source uploads stay immutable. `run_session` computes the next
result before replacing displayed state; failed runs preserve a clear error state.
