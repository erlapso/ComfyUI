import pytest
from aiohttp import web
from api_server.routes.internal.internal_routes import InternalRoutes
from api_server.routes.internal import internal_routes
import app.logger

@pytest.mark.asyncio
async def test_get_folder_paths(aiohttp_client):
    """
    Test the /folder_paths endpoint to ensure it returns a mapping where each key maps
    to the first element of the corresponding value from folder_names_and_paths.
    """
    test_mapping = {"test": ["value"], "demo": ["sample_value", "other"]}
    internal_routes.folder_names_and_paths = test_mapping
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/folder_paths')
    assert resp.status == 200
    data = await resp.json()
    expected = {"test": "value", "demo": "sample_value"}
    assert data == expected
@pytest.mark.asyncio
async def test_logs_subscribe(monkeypatch, aiohttp_client):
    """
    Test the /logs/subscribe endpoint to ensure that the terminal_service's subscribe and unsubscribe
    methods are called appropriately based on the 'enabled' flag.
    """
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    subscribe_called = []
    unsubscribe_called = []
    internal.terminal_service.subscribe = lambda client_id: subscribe_called.append(client_id)
    internal.terminal_service.unsubscribe = lambda client_id: unsubscribe_called.append(client_id)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.patch('/logs/subscribe', json={"clientId": "client1", "enabled": True})
    assert resp.status == 200
    assert subscribe_called == ["client1"]
    assert unsubscribe_called == []
    resp = await client.patch('/logs/subscribe', json={"clientId": "client1", "enabled": False})
    assert resp.status == 200
    assert unsubscribe_called == ["client1"]
@pytest.mark.asyncio
async def test_get_raw_logs(monkeypatch, aiohttp_client):
    """
    Test the /logs/raw endpoint to ensure that it returns the list of log entries
    provided by app.logger.get_logs and the updated terminal size from terminal_service.
    """
    fake_logs = [
        {"t": "2023-10-01 12:00", "m": "Log entry 1"},
        {"t": "2023-10-01 12:01", "m": "Log entry 2"}
    ]
    monkeypatch.setattr(internal_routes.app.logger, "get_logs", lambda: fake_logs)
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    def fake_update_size():
        internal.terminal_service.cols = 100
        internal.terminal_service.rows = 40
    internal.terminal_service.update_size = fake_update_size
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/logs/raw')
    assert resp.status == 200
    data = await resp.json()
    expected = {
        "entries": fake_logs,
        "size": {"cols": 100, "rows": 40}
    }
    assert data == expected
@pytest.mark.asyncio
async def test_get_logs(monkeypatch, aiohttp_client):
    """
    Test the /logs endpoint to ensure it returns a concatenated string of log entries.
    """
    fake_logs = [
        {"t": "TIME1", "m": "MESSAGE1"},
        {"t": "TIME2", "m": "MESSAGE2"}
    ]
    monkeypatch.setattr(app.logger, "get_logs", lambda: fake_logs)
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/logs')
    assert resp.status == 200
    data = await resp.json()
    expected = "".join([entry["t"] + " - " + entry["m"] for entry in fake_logs])
    assert data == expected
@pytest.mark.asyncio
async def test_logs_subscribe_invalid_json(aiohttp_client):
    """
    Test the /logs/subscribe endpoint by sending an invalid JSON payload (missing required keys)
    to ensure that it results in a 500 Internal Server Error.
    """
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.patch('/logs/subscribe', json={})
    assert resp.status == 500
@pytest.mark.asyncio
async def test_get_app_multiple_calls(aiohttp_client):
    """
    Test that calling get_app() multiple times returns the same app instance and only registers routes once.
    Since aiohttp auto-generates HEAD routes for GET endpoints, we filter them out before counting.
    Expected endpoints: /logs (GET), /logs/raw (GET), /folder_paths (GET), and /logs/subscribe (PATCH).
    """
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app1 = internal.get_app()
    app2 = internal.get_app()
    assert app1 is app2
    filtered_routes = [route for route in app1.router.routes() if getattr(route, "method", None) != "HEAD"]
    expected_route_count = 4
    assert len(filtered_routes) == expected_route_count
@pytest.mark.asyncio
async def test_get_logs_bad_format(monkeypatch, aiohttp_client):
    """
    Test the /logs endpoint to ensure that if log entries are missing required keys,
    the server returns a 500 Internal Server Error.
    """
    bad_logs = [{"x": "VALUE"}]
    monkeypatch.setattr(internal_routes.app.logger, "get_logs", lambda: bad_logs)
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/logs')
    assert resp.status == 500
@pytest.mark.asyncio
async def test_method_not_allowed_on_logs_subscribe(aiohttp_client):
    """
    Test that sending a GET request to the PATCH-only /logs/subscribe endpoint returns a 405 Method Not Allowed.
    """
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/logs/subscribe')
    assert resp.status == 405
@pytest.mark.asyncio
async def test_get_logs_empty(monkeypatch, aiohttp_client):
    """
    Test that the /logs endpoint returns an empty string when there are no log entries.
    """
    monkeypatch.setattr(internal_routes.app.logger, "get_logs", lambda: [])
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/logs')
    assert resp.status == 200
    data = await resp.json()
    assert data == ""
@pytest.mark.asyncio
async def test_get_folder_paths_empty_value(aiohttp_client):
    """
    Test that the /folder_paths endpoint returns a 500 error
    when a folder path mapping contains an empty list, causing IndexError
    when trying to access the first element.
    """
    test_mapping = {"empty_key": []}
    from api_server.routes.internal import internal_routes
    internal_routes.folder_names_and_paths = test_mapping
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/folder_paths')
    assert resp.status == 500
@pytest.mark.asyncio
async def test_get_folder_paths_empty_mapping(aiohttp_client):
    """
    Test that the /folder_paths endpoint returns an empty JSON object
    when the folder_names_and_paths mapping is empty.
    """
    internal_routes.folder_names_and_paths = {}
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/folder_paths')
    assert resp.status == 200
    # Additional GET requests to confirm the empty mapping response
    data = await resp.json()
    assert data == {}
@pytest.mark.asyncio
async def test_logs_subscribe_numeric_enabled(aiohttp_client):
    """
    Test the /logs/subscribe endpoint with numeric 'enabled' field.
    A numeric non-zero should invoke subscribe and 0 should invoke unsubscribe.
    """
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    subscribe_called = []
    unsubscribe_called = []
    internal.terminal_service.subscribe = lambda client_id: subscribe_called.append(client_id)
    internal.terminal_service.unsubscribe = lambda client_id: unsubscribe_called.append(client_id)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.patch('/logs/subscribe', json={"clientId": "numeric_client", "enabled": 1})
    assert resp.status == 200
    assert subscribe_called == ["numeric_client"]
    assert unsubscribe_called == []
    subscribe_called.clear()
    unsubscribe_called.clear()
    resp = await client.patch('/logs/subscribe', json={"clientId": "numeric_client", "enabled": 0})
    assert resp.status == 200
    assert unsubscribe_called == ["numeric_client"]
    assert subscribe_called == []
@pytest.mark.asyncio
async def test_method_not_allowed_on_folder_paths(aiohttp_client):
    """
    Test that sending a POST request to the GET-only /folder_paths endpoint returns a 405 Method Not Allowed.
    This ensures that only supported HTTP methods are accepted.
    """
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.post('/folder_paths')
    assert resp.status == 405
@pytest.mark.asyncio
async def test_logs_subscribe_invalid_json_format(aiohttp_client):
    """
    Test that sending an invalid JSON payload (plain text instead of valid JSON)
    to the /logs/subscribe endpoint results in a 500 Internal Server Error.
    """
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    # Sending a request with an invalid JSON body text.
    resp = await client.patch('/logs/subscribe', data="not a json", headers={"Content-Type": "text/plain"})
    assert resp.status == 500
@pytest.mark.asyncio
async def test_get_raw_logs_update_size_exception(monkeypatch, aiohttp_client):
    """
    Test that the /logs/raw endpoint returns a 500 Internal Server Error when 
    terminal_service.update_size raises an exception.
    """
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    def fake_update_size():
        raise Exception("Update size error")
    internal.terminal_service.update_size = fake_update_size
    monkeypatch.setattr(internal_routes.app.logger, "get_logs", lambda: [])
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/logs/raw')
    assert resp.status == 500
@pytest.mark.asyncio
async def test_get_folder_paths_invalid_value_type(aiohttp_client):
    """
    Test that the /folder_paths endpoint returns a 500 Internal Server Error when 
    a folder path mapping value is not subscriptable (e.g. an integer), causing an exception.
    """
    internal_routes.folder_names_and_paths = {"invalid": 123}
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/folder_paths')
    assert resp.status == 500
@pytest.mark.asyncio
async def test_get_logs_none(monkeypatch, aiohttp_client):
    """
    Test the /logs endpoint when app.logger.get_logs returns None.
    This test ensures that if get_logs returns None (an unexpected type), the server raises an exception,
    which results in a 500 Internal Server Error.
    """
    monkeypatch.setattr(app.logger, "get_logs", lambda: None)
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/logs')
    assert resp.status == 500
@pytest.mark.asyncio
async def test_method_not_allowed_on_logs(aiohttp_client):
    """
    Test that sending a POST request to the GET-only /logs endpoint 
    returns a 405 Method Not Allowed error.
    """
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.post('/logs')
    assert resp.status == 405
@pytest.mark.asyncio
async def test_logs_subscribe_extra_keys(aiohttp_client):
    """
    Test that the /logs/subscribe endpoint correctly processes a JSON payload containing extra keys.
    This verifies that extra keys are ignored and the subscribe/unsubscribe methods are invoked
    based solely on the 'enabled' flag.
    """
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    subscribe_called = []
    unsubscribe_called = []
    internal.terminal_service.subscribe = lambda client_id: subscribe_called.append(client_id)
    internal.terminal_service.unsubscribe = lambda client_id: unsubscribe_called.append(client_id)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.patch('/logs/subscribe',
                              json={"clientId": "client_extra", "enabled": True, "extra": "ignore_this"})
    assert resp.status == 200
    assert subscribe_called == ["client_extra"]
    assert unsubscribe_called == []
    subscribe_called.clear()
    unsubscribe_called.clear()
    resp = await client.patch('/logs/subscribe',
                              json={"clientId": "client_extra", "enabled": False, "extra": "ignore_this"})
    assert resp.status == 200
    assert unsubscribe_called == ["client_extra"]
    assert subscribe_called == []
@pytest.mark.asyncio
async def test_logs_subscribe_exception(monkeypatch, aiohttp_client):
    """
    Test that the /logs/subscribe endpoint returns a 500 Internal Server Error
    when the terminal_service.subscribe method raises an exception.
    """
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    def faulty_subscribe(client_id):
        raise Exception("subscribe error")
    internal.terminal_service.subscribe = faulty_subscribe
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.patch('/logs/subscribe', json={"clientId": "client_error", "enabled": True})
    assert resp.status == 500
@pytest.mark.asyncio
async def test_get_folder_paths_none_value(aiohttp_client):
    """
    Test that the /folder_paths endpoint returns a 500 error when folder_names_and_paths is None.
    This simulates a misconfiguration where the mapping is not provided.
    """
    internal_routes.folder_names_and_paths = None
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/folder_paths')
    assert resp.status == 500
@pytest.mark.asyncio
async def test_get_logs_non_iterable(monkeypatch, aiohttp_client):
    """
    Test that the /logs endpoint returns a 500 Internal Server Error
    when app.logger.get_logs returns a non-iterable value (e.g., an integer),
    which would cause a TypeError in the list comprehension.
    """
    monkeypatch.setattr(app.logger, "get_logs", lambda: 123)
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/logs')
    assert resp.status == 500
@pytest.mark.asyncio
async def test_get_logs_with_none_entry(monkeypatch, aiohttp_client):
    """
    Test the /logs endpoint to ensure that if one of the log entries is None,
    it results in a 500 Internal Server Error.
    """
    monkeypatch.setattr(app.logger, "get_logs", lambda: [None, {"t": "TIME", "m": "MESSAGE"}])
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/logs')
    assert resp.status == 500
@pytest.mark.asyncio
async def test_get_logs_invalid_entry_type(monkeypatch, aiohttp_client):
    """
    Test the /logs endpoint when one of the log entries is not a dictionary.
    This ensures that the server returns a 500 Internal Server Error
    when encountering an invalid log entry type.
    """
    monkeypatch.setattr(app.logger, "get_logs", lambda: ["not a dict", {"t": "TIME", "m": "MESSAGE"}])
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/logs')
    assert resp.status == 500
@pytest.mark.asyncio
async def test_get_raw_logs_with_generator(aiohttp_client, monkeypatch):
    """
    Test the /logs/raw endpoint when app.logger.get_logs returns a generator.
    This verifies that the endpoint correctly converts the generator to a list and returns the expected JSON payload.
    """
    def gen_logs():
        yield {"t": "2023-10-01 12:00", "m": "Generator log entry 1"}
        yield {"t": "2023-10-01 12:01", "m": "Generator log entry 2"}
    monkeypatch.setattr(app.logger, "get_logs", lambda: gen_logs())
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    def fake_update_size():
        internal.terminal_service.cols = 80
        internal.terminal_service.rows = 24
    internal.terminal_service.update_size = fake_update_size
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/logs/raw')
    assert resp.status == 200
    data = await resp.json()
    expected = {
        "entries": [
            {"t": "2023-10-01 12:00", "m": "Generator log entry 1"},
            {"t": "2023-10-01 12:01", "m": "Generator log entry 2"}
        ],
        "size": {"cols": 80, "rows": 24}
    }
    assert data == expected
@pytest.mark.asyncio
async def test_logs_subscribe_enabled_string(aiohttp_client):
    """
    Test the /logs/subscribe endpoint when the 'enabled' field is provided as a string.
    A non-empty string should be truthy, causing the subscribe method to be invoked, while an
    empty string should be falsy and cause the unsubscribe method to be called.
    """
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    subscribe_called = []
    unsubscribe_called = []
    internal.terminal_service.subscribe = lambda client_id: subscribe_called.append(client_id)
    internal.terminal_service.unsubscribe = lambda client_id: unsubscribe_called.append(client_id)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    
    resp = await client.patch('/logs/subscribe', json={"clientId": "client_str", "enabled": "yes"})
    assert resp.status == 200
    assert subscribe_called == ["client_str"]
    assert unsubscribe_called == []
    
    subscribe_called.clear()
    unsubscribe_called.clear()
    
    resp = await client.patch('/logs/subscribe', json={"clientId": "client_str", "enabled": ""})
    assert resp.status == 200
    assert unsubscribe_called == ["client_str"]
    assert subscribe_called == []
@pytest.mark.asyncio
async def test_get_logs_non_string_values(monkeypatch, aiohttp_client):
    """
    Test the /logs endpoint returns a 500 Internal Server Error 
    when the log entries contain non-string values for 't' or 'm'.
    This ensures that the server fails when concatenation of non-string types is attempted.
    """
    monkeypatch.setattr(app.logger, "get_logs", lambda: [{"t": 123, "m": 456}])
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/logs')
    assert resp.status == 500
@pytest.mark.asyncio
async def test_get_folder_paths_invalid_mapping_type(aiohttp_client):
    """
    Test that the /folder_paths endpoint returns a 500 Internal Server Error 
    when folder_names_and_paths is not a mapping (for example, when it is a list),
    causing a runtime error during iteration or indexing.
    """
    internal_routes.folder_names_and_paths = ["not", "a", "dict"]
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/folder_paths')
    assert resp.status == 500
@pytest.mark.asyncio
async def test_get_raw_logs_non_iterable(monkeypatch, aiohttp_client):
    """
    Test that the /logs/raw endpoint returns a 500 Internal Server Error
    when app.logger.get_logs returns None (a non-iterable), because list(None) will raise a TypeError.
    """
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    def fake_update_size():
        internal.terminal_service.cols = 80
        internal.terminal_service.rows = 24
    internal.terminal_service.update_size = fake_update_size
    monkeypatch.setattr(internal_routes.app.logger, "get_logs", lambda: None)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/logs/raw')
    assert resp.status == 500
@pytest.mark.asyncio
async def test_get_raw_logs_update_size_called(monkeypatch, aiohttp_client):
    """
    Test that the /logs/raw endpoint calls terminal_service.update_size exactly once and returns the updated terminal size.
    We verify update_size is called by incrementing a counter and then confirm the response JSON contains the expected values.
    """
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    call_count = [0]
    def spy_update_size():
        call_count[0] += 1
        internal.terminal_service.cols = 80
        internal.terminal_service.rows = 24
    internal.terminal_service.update_size = spy_update_size
    monkeypatch.setattr(app.logger, "get_logs", lambda: [])
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/logs/raw')
    assert resp.status == 200
    data = await resp.json()
    assert call_count[0] == 1
    expected = {
        "entries": [],
        "size": {"cols": 80, "rows": 24}
    }
    assert data == expected
@pytest.mark.asyncio
async def test_get_folder_paths_none_first_element(aiohttp_client):
    """
    Test the /folder_paths endpoint when a mapping value is a list whose first element is None.
    This verifies that the endpoint returns a JSON mapping with None (null in JSON) for that key.
    """
    test_mapping = {"key_with_none": [None], "valid_key": ["valid_value"]}
    internal_routes.folder_names_and_paths = test_mapping
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    
    resp = await client.get('/folder_paths')
    assert resp.status == 200
    data = await resp.json()
    expected = {"key_with_none": None, "valid_key": "valid_value"}
    assert data == expected
@pytest.mark.asyncio
async def test_get_logs_with_string_return(monkeypatch, aiohttp_client):
    """
    Test that the /logs endpoint returns a 500 Internal Server Error
    when app.logger.get_logs returns a string instead of an iterable of dictionaries.
    This simulates a scenario where the log data is of the wrong type,
    causing a TypeError during concatenation.
    """
    monkeypatch.setattr(app.logger, "get_logs", lambda: "this is a log")
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/logs')
    assert resp.status == 500
@pytest.mark.asyncio
async def test_get_logs_exception_during_get_logs(monkeypatch, aiohttp_client):
    """
    Test that the /logs endpoint returns a 500 Internal Server Error
    when app.logger.get_logs raises an exception during its execution.
    """
    def fake_get_logs():
        raise Exception("Simulated error in get_logs")
    monkeypatch.setattr(app.logger, "get_logs", fake_get_logs)
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/logs')
    assert resp.status == 500
@pytest.mark.asyncio
async def test_get_logs_generator(monkeypatch, aiohttp_client):
    """
    Test the /logs endpoint when app.logger.get_logs returns a generator.
    This verifies that the endpoint correctly iterates over a generator, concatenating
    each log entry in the format 't - m', and returns the expected string as JSON.
    """
    def gen_logs():
        yield {"t": "TIME1", "m": "MESSAGE1"}
        yield {"t": "TIME2", "m": "MESSAGE2"}
        
    monkeypatch.setattr(app.logger, "get_logs", lambda: gen_logs())
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/logs')
    assert resp.status == 200
    data = await resp.json()
    expected = "TIME1 - MESSAGE1TIME2 - MESSAGE2"
    assert data == expected
@pytest.mark.asyncio
async def test_get_logs_with_tuple(aiohttp_client, monkeypatch):
    """
    Test the /logs endpoint when app.logger.get_logs returns a tuple of log entries.
    This verifies that tuple iterables are handled correctly and the entries are concatenated into a string.
    """
    fake_logs = (
        {"t": "2023-10-02 10:00", "m": "Tuple log entry 1"},
        {"t": "2023-10-02 10:01", "m": "Tuple log entry 2"}
    )
    monkeypatch.setattr(app.logger, "get_logs", lambda: fake_logs)
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/logs')
    assert resp.status == 200
    data = await resp.json()
    expected = "2023-10-02 10:00 - Tuple log entry 12023-10-02 10:01 - Tuple log entry 2"
    assert data == expected
@pytest.mark.asyncio
async def test_get_folder_paths_tuple_values(aiohttp_client):
    """
    Test the /folder_paths endpoint when folder_names_and_paths contains tuple values.
    This ensures that the endpoint correctly handles non-list subscriptable iterables by
    returning the first element of the tuple.
    """
    # Setup folder_names_and_paths mapping with a tuple value.
    test_mapping = {"tuple_key": ("tuple_value", "second_value")}
    internal_routes.folder_names_and_paths = test_mapping
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/folder_paths')
    assert resp.status == 200
    data = await resp.json()
    expected = {"tuple_key": "tuple_value"}
    assert data == expected
@pytest.mark.asyncio
async def test_logs_subscribe_none_enabled(aiohttp_client):
    """
    Test that the /logs/subscribe endpoint processes a JSON payload with 'enabled' set to None,
    treating it as a falsy value and calling the unsubscribe method.
    """
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    subscribe_called = []
    unsubscribe_called = []
    # Override the subscribe and unsubscribe methods for testing
    internal.terminal_service.subscribe = lambda client_id: subscribe_called.append(client_id)
    internal.terminal_service.unsubscribe = lambda client_id: unsubscribe_called.append(client_id)
    
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.patch('/logs/subscribe', json={"clientId": "client_none", "enabled": None})
    assert resp.status == 200
    # With "enabled": None, the value is falsy, so unsubscribe should be called.
    assert subscribe_called == []
    assert unsubscribe_called == ["client_none"]
@pytest.mark.asyncio
async def test_get_folder_paths_empty_tuple(aiohttp_client):
    """
    Test that the /folder_paths endpoint returns a 500 Internal Server Error
    when a folder path mapping value is an empty tuple, which raises an IndexError
    when trying to access the first element.
    """
    # Set folder_names_and_paths with an empty tuple as the value.
    test_mapping = {"empty_tuple": ()}
    internal_routes.folder_names_and_paths = test_mapping
    
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    
    resp = await client.get('/folder_paths')
    assert resp.status == 500
@pytest.mark.asyncio
async def test_get_raw_logs_update_size_not_callable(aiohttp_client, monkeypatch):
    """
    Test the /logs/raw endpoint when terminal_service.update_size is not callable.
    This simulates a misconfiguration where update_size is set incorrectly (None) and verifies that
    the endpoint returns a 500 Internal Server Error.
    """
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    # Set update_size to a non-callable value
    internal.terminal_service.update_size = None
    # Override logger.get_logs to return an empty list to avoid interference from logger errors
    monkeypatch.setattr(internal_routes.app.logger, "get_logs", lambda: [])
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/logs/raw')
    assert resp.status == 500
@pytest.mark.asyncio
async def test_logs_subscribe_unsubscribe_exception(aiohttp_client):
    """
    Test that the /logs/subscribe endpoint returns a 500 Internal Server Error
    when terminal_service.unsubscribe raises an exception.
    """
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    
    # Monkeypatch the unsubscribe method to raise an exception.
    def faulty_unsubscribe(client_id):
        raise Exception("unsubscribe error")
        
    internal.terminal_service.unsubscribe = faulty_unsubscribe
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    
    # When unsubscribe raises an exception, the PATCH should yield a 500 status.
    resp = await client.patch('/logs/subscribe', json={"clientId": "client_error", "enabled": False})
    assert resp.status == 500
@pytest.mark.asyncio
async def test_get_raw_logs_exception_in_get_logs(monkeypatch, aiohttp_client):
    """
    Test that the /logs/raw endpoint returns a 500 Internal Server Error when
    app.logger.get_logs() raises an exception. This simulates a scenario where the
    log retrieval fails after terminal_service.update_size is called.
    """
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    
    # Setup terminal_service.update_size to set valid terminal size values.
    def fake_update_size():
        internal.terminal_service.cols = 80
        internal.terminal_service.rows = 24
    internal.terminal_service.update_size = fake_update_size
    
    # Monkeypatch app.logger.get_logs to raise an exception.
    def raise_error():
        raise Exception("Simulated get_logs error")
    monkeypatch.setattr(internal_routes.app.logger, "get_logs", raise_error)
    
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    resp = await client.get('/logs/raw')
    assert resp.status == 500
@pytest.mark.asyncio
async def test_get_folder_paths_numeric_first_element(aiohttp_client):
    """
    Test that the /folder_paths endpoint returns correct JSON mapping when a folder path mapping's
    first element is a numeric value and other types such as string are present.
    """
    # Set up folder_names_and_paths with a numeric and a string first element.
    test_mapping = {"num_key": [42], "str_key": ["hello"]}
    internal_routes.folder_names_and_paths = test_mapping
    
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    
    client = await aiohttp_client(app_instance)
    resp = await client.get('/folder_paths')
    assert resp.status == 200
    data = await resp.json()
    
    expected = {"num_key": 42, "str_key": "hello"}
    assert data == expected
@pytest.mark.asyncio
async def test_logs_subscribe_with_list_json(aiohttp_client):
    """
    Test that sending a JSON payload that is a list (instead of a dict) 
    to the /logs/subscribe endpoint results in a 500 Internal Server Error.
    """
    dummy_prompt_server = object()
    internal = InternalRoutes(dummy_prompt_server)
    app_instance = internal.get_app()
    client = await aiohttp_client(app_instance)
    # Sending a JSON payload that is a list rather than a dictionary.
    resp = await client.patch('/logs/subscribe', json=[1, 2, 3])
    assert resp.status == 500