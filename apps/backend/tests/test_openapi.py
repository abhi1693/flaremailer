from __future__ import annotations

from fastapi import FastAPI


def test_openapi_operation_ids_are_explicit_and_unique(app: FastAPI) -> None:
    schema = app.openapi()
    operation_ids: list[str] = []
    for path_item in schema["paths"].values():
        for method, operation in path_item.items():
            if method in {"get", "post", "patch", "delete"}:
                operation_ids.append(operation["operationId"])
    assert len(operation_ids) == len(set(operation_ids))
    assert "emailsEnqueue" in operation_ids
    assert "templatesPreview" in operation_ids
    assert schema["paths"]["/api/v1/emails"]["post"]["tags"] == ["emails"]
