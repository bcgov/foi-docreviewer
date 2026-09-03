from messaging import state


def test_get_state_client_is_process_wide_and_lazy():
    """
    Lazily constructed: importing the module must not open a socket, or every
    importer needs a live Redis. Same instance thereafter, so handlers share
    one connection pool rather than one per message.
    """
    assert state._client is None

    first = state.get_state_client()
    second = state.get_state_client()

    assert first is second
    assert state._client is first


async def test_close_state_client_resets_the_global():
    state.get_state_client()
    await state.close_state_client()
    assert state._client is None
