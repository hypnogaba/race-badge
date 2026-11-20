# Packs app files into gzip+base64 JSON for pasting into the emulator page.
import base64, gzip, json, os, sys
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
files = sys.argv[1:] or ["app.json", "art.lua", "main.lua"]
data = {f: open(os.path.join(root, f)).read() for f in files}
blob = base64.b64encode(gzip.compress(json.dumps(data).encode(), 9)).decode()
open(os.path.join(root, "tools", "out", "bundle.b64"), "w").write(blob)
print(len(blob))
