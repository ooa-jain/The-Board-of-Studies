/**
 * BoS Portal — uploaded files into Google Drive.
 *
 * Paste into a new project at script.google.com (signed in as the Drive's
 * owner), add the script property SECRET (Project Settings > Script
 * Properties), and deploy as a Web app: Execute as "Me", access "Anyone".
 * Put the /exec URL and the same SECRET in the portal's .env as
 * DRIVE_SCRIPT_URL and DRIVE_SCRIPT_SECRET. See app/drive_store.py.
 *
 * Files go into "BoS Portal Files" / year / department / stage.
 */
const ROOT_NAME = 'BoS Portal Files';
const props = () => PropertiesService.getScriptProperties();

function root_() {
  const id = props().getProperty('ROOT');
  if (id) { try { return DriveApp.getFolderById(id); } catch (e) {} }
  const f = DriveApp.createFolder(ROOT_NAME);
  props().setProperty('ROOT', f.getId());
  return f;
}

function folder_(path) {
  let f = root_();
  String(path || '').split('/').filter(String).forEach(n => {
    const it = f.getFoldersByName(n);
    f = it.hasNext() ? it.next() : f.createFolder(n);
  });
  return f;
}

const out_ = o => ContentService.createTextOutput(JSON.stringify(o))
  .setMimeType(ContentService.MimeType.JSON);

function doPost(e) {
  try {
    const b = JSON.parse(e.postData.contents);
    if (!b.secret || b.secret !== props().getProperty('SECRET')) return out_({ ok: false, error: 'forbidden' });
    if (b.action === 'ping') return out_({ ok: true, root: root_().getId() });
    if (b.action === 'put') {
      const blob = Utilities.newBlob(Utilities.base64Decode(b.data), b.mime || 'application/octet-stream', b.name);
      return out_({ ok: true, id: folder_(b.path).createFile(blob).getId() });
    }
    if (b.action === 'get') {
      const f = DriveApp.getFileById(b.id);
      return out_({ ok: true, name: f.getName(), mime: f.getMimeType(),
                    data: Utilities.base64Encode(f.getBlob().getBytes()) });
    }
    if (b.action === 'trash') { DriveApp.getFileById(b.id).setTrashed(true); return out_({ ok: true }); }
    return out_({ ok: false, error: 'unknown action' });
  } catch (err) {
    return out_({ ok: false, error: String(err) });
  }
}
