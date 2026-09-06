from ide.app import create_app


def _client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_compile_endpoint_returns_tree_and_symbols_for_valid_program():
    response = _client().post(
        "/compile",
        json={"source": "let value: integer = 1; print(value);"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["errors"] == []
    assert payload["tree"]["label"] == "program"
    assert any(symbol["name"] == "value" for symbol in payload["symbols"])


def test_compile_endpoint_reports_semantic_errors():
    response = _client().post("/compile", json={"source": "print(missing);"})

    payload = response.get_json()
    assert payload["success"] is False
    assert payload["errors"][0]["category"] == "semantico"
    assert payload["errors"][0]["rule"] == "uso-variable-no-declarada"


def test_compile_endpoint_reports_lexical_and_syntax_errors():
    lexical = _client().post("/compile", json={"source": "@"}).get_json()
    syntax = _client().post("/compile", json={"source": "let value = ;"}).get_json()

    assert any(error["category"] == "lexico" for error in lexical["errors"])
    assert any(error["category"] == "sintactico" for error in syntax["errors"])


def test_compile_endpoint_rejects_invalid_payload():
    response = _client().post("/compile", json={"code": "print(1);"})

    assert response.status_code == 400
    assert "source" in response.get_json()["error"]


def test_index_serves_the_ide():
    response = _client().get("/")

    assert response.status_code == 200
    assert b"Compiscript IDE" in response.data
