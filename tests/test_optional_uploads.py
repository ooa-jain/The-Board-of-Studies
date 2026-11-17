"""The Office can make an upload box not mandatory (Admin → Keywords): a
department may then leave it empty and still submit."""

from test_workflow import DEPT_INFO_OK, login, make_department


def test_the_office_makes_an_upload_box_not_mandatory(app, client):
    login(client, app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    page = client.get("/admin/keywords").get_data(as_text=True)
    assert 'name="mand_pre_bos_minutes"' in page and "Mandatory" in page
    # the optional box has no switch: it is optional already
    assert 'name="mand_feedback_new_programme"' not in page
    # every mandatory box stays on but the Pre-BoS minutes
    from app.keyword_match import upload_boxes
    form = {f"mand_{b['field']}": "1" for b in upload_boxes() if b["required"] and b["field"] != "pre_bos_minutes"}
    r = client.post("/admin/keywords", data=form)
    assert r.status_code == 302
    from app.db import get_db
    with app.app_context():
        assert get_db().settings.find_one({"_id": "app"})["optional_uploads"] == ["pre_bos_minutes"]
    page = client.get("/admin/keywords").get_data(as_text=True)
    import re
    tag = re.search(r'<input type="checkbox" name="mand_pre_bos_minutes"[^>]*>', page).group(0)
    assert "checked" not in tag                                               # shown off
    assert "checked" in re.search(r'<input type="checkbox" name="mand_diac_signed"[^>]*>', page).group(0)
    client.get("/logout")

    # the department: no star on it, and Submit goes through without it
    u, p = make_department(app)
    login(client, u, p)
    assert client.post("/department/api/dept_info/submit", json=DEPT_INFO_OK).get_json()["ok"]
    page = client.get("/department/stage/pre_bos").get_data(as_text=True)
    import json
    stage = json.loads(page.split('<script id="stage-def" type="application/json">')[1].split("</script>")[0])
    req = {f["name"]: f.get("required") for s in stage["sections"] for f in s.get("fields", [])}
    assert req["pre_bos_minutes"] is False and req["diac_signed"] is True
    up = lambda name: {"name": name, "stored": "x-" + name, "size": 900}
    data = {"pre_bos_files": {"diac_signed": up("diac.pdf"), "dpac_signed": up("pac.pdf")}}
    j = client.post("/department/api/pre_bos/validate", json=data).get_json()
    assert not [i for i in j["issues"] if "Minutes" in i["message"] and i["level"] == "error"], j["issues"]
    # a box still mandatory is still asked for
    j = client.post("/department/api/pre_bos/validate", json={"pre_bos_files": {}}).get_json()
    assert any("Industry-Academia" in i["message"] and i["level"] == "error" for i in j["issues"])
