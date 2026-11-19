"""POs: 7 to 12 (a warning below 7, 12 at most); PSOs can be marked not
applicable, and then each course's mapping is a CO-PO Mapping."""

from test_workflow import login, make_department


def _profile_issues(client, profile):
    body = client.post("/department/api/prog_curriculum/BCMREG/validate", json={"profile": profile}).get_json()
    return [i for i in body.get("issues", []) if i.get("section") == "profile"]


def test_pos_seven_to_twelve(app, client):
    from app.schema import PO_MAX, STAGE_BY_KEY
    assert PO_MAX == 12
    u, p = make_department(app)
    login(client, u, p)
    few = _profile_issues(client, {"programme_outcomes": ["a", "b", "c"]})
    assert any(i["level"] == "warning" and "7 to 12" in i["message"] for i in few)
    many = _profile_issues(client, {"programme_outcomes": [str(n) for n in range(13)]})
    assert any(i["level"] == "error" and "at most 12" in i["message"] for i in many)
    seven = _profile_issues(client, {"programme_outcomes": [str(n) for n in range(7)]})
    assert not any("7 to 12" in i["message"] for i in seven)


def test_pso_not_applicable(app, client):
    from app.schema import mapping_title, programme_columns
    u, p = make_department(app)
    login(client, u, p)
    need = _profile_issues(client, {"programme_outcomes": ["a"]})
    assert any("PSO" in i["message"] for i in need)
    na = _profile_issues(client, {"programme_outcomes": ["a"], "pso_na": True})
    assert not any("Programme Specific Outcomes" in i["message"] for i in na)

    prof = {"programme_outcomes": ["a", "b"], "programme_specific_outcomes": ["x"], "pso_na": True}
    cols = [n for n, _ in programme_columns(prof)]
    assert cols == ["PO1", "PO2"] and mapping_title(cols) == "CO-PO Mapping"
    prof["pso_na"] = False
    cols = [n for n, _ in programme_columns(prof)]
    assert cols == ["PO1", "PO2", "PSO1"] and mapping_title(cols) == "CO-PO-PSO Mapping"
