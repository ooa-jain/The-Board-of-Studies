"""The signed DIAC and PAC forms: each upload is checked against the
university's template, and a form with categories left blank is named
and cannot be submitted."""

import io
import tempfile
from pathlib import Path

from test_workflow import DEPT_INFO_OK, login, make_department

ROOT = Path(__file__).resolve().parent.parent / "app" / "static" / "templates"
DIAC, PAC = ROOT / "Composition_of_DIAC.docx", ROOT / "Composition_of_PAC.docx"


def _filled(src, field, skip=()):
    from app.template_check import fill
    out = Path(tempfile.mkdtemp()) / "form.docx"
    return fill(src, out, field, skip=skip).read_bytes()


def _up(client, name, data, field):
    return client.post("/department/api/upload", data={
        "file": (io.BytesIO(data), name), "stage": "pre_bos", "field": field,
    }, content_type="multipart/form-data").get_json()


def test_the_empty_template_is_all_blank():
    from app.template_check import check, problems
    r = check(DIAC, "diac_signed")
    assert r["filled"] == 0 and r["total"] == 7 and r["placeholders"] == 7
    assert "Blank — fill Dean of Faculty / Director of School" in problems(r)[0]
    r = check(PAC, "dpac_signed")
    assert r["total"] == 14 and "Academician" in r["blank"]


def test_a_filled_form_passes_and_a_half_filled_one_names_the_gaps():
    from app.template_check import check, problems
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "x.docx"
        p.write_bytes(_filled(PAC, "dpac_signed"))
        assert check(p, "dpac_signed")["ok"]
        p.write_bytes(_filled(PAC, "dpac_signed", skip=["Alumni", "Parent"]))
        r = check(p, "dpac_signed")
        assert r["blank"] == ["Alumni", "Parent"] and not r["ok"]
        assert problems(r) == ["Blank — fill Alumni, Parent"]


def test_a_blank_form_cannot_be_submitted(app, client):
    u, p = make_department(app)
    login(client, u, p)
    assert client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK).get_json()["ok"]

    diac = _up(client, "diac.docx", _filled(DIAC, "diac_signed", skip=["Alumni"]), "diac_signed")
    assert diac["match"]["template"]["blank"] == ["Alumni"]
    dpac = _up(client, "pac.docx", _filled(PAC, "dpac_signed"), "dpac_signed")
    assert dpac["match"]["template"]["ok"]

    data = {"pre_bos_files": {"diac_signed": diac, "dpac_signed": dpac,
                              "pre_bos_minutes": {"name": "minutes.pdf", "stored": "x-minutes.pdf", "size": 900}}}
    # a blank form still saves — only submitting is refused
    assert client.post("/department/api/pre_bos/save", json=data).get_json()["ok"]
    j = client.post("/department/api/pre_bos/validate", json=data).get_json()
    assert any("Blank — fill Alumni" in i["message"] for i in j["issues"])
    j = client.post("/department/api/pre_bos/submit", json=data).get_json()
    assert not j["ok"] and any("Blank — fill Alumni" in i["message"] for i in j["issues"])

    # filled in and uploaded again: it goes through
    diac = _up(client, "diac.docx", _filled(DIAC, "diac_signed"), "diac_signed")
    data["pre_bos_files"]["diac_signed"] = diac
    assert client.post("/department/api/pre_bos/submit", json=data).get_json()["ok"]


def test_the_templates_can_be_downloaded(client):
    r = client.get("/static/templates/Composition_of_DIAC.docx")
    assert r.status_code == 200 and r.data[:2] == b"PK"
