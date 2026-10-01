import os
import threading
import webbrowser
import json

from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from compiler.gui_bridge import repair_source_for_gui, repair_source_for_gui_stream
from compiler.week5_repair_helpers import print_parser_check

# Startup check for parser freshness
print_parser_check()

app = Flask(
    __name__,
    template_folder="gui/templates",
    static_folder="gui/static"
)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/repair", methods=["POST"])
def repair():
    data = request.json or {}
    code = data.get("code", "")
    filename = data.get("filename", "main.c")

    result = repair_source_for_gui(code, filename)
    return jsonify(result)


@app.route("/api/repair_stream", methods=["POST"])
def repair_stream():
    data = request.json or {}
    code = data.get("code", "")
    filename = data.get("filename", "main.c")

    @stream_with_context
    def generate():
        for event in repair_source_for_gui_stream(code, filename):
            yield f"data: {json.dumps(event)}\n\n"

    return Response(generate(), mimetype="text/event-stream")

@app.route("/api/testcase", methods=["POST"])
def testcase():
    data = request.json or {}
    code = data.get("code", "")
    filename = data.get("filename", "test_case.c")

    result = repair_source_for_gui(code, filename)
    return jsonify(result)


@app.route("/api/examples")
def examples():
    example_root = "examples"
    files = []

    if os.path.exists(example_root):
        for root, _, filenames in os.walk(example_root):
            for f in filenames:
                if f.endswith(".c"):
                    rel_path = os.path.relpath(os.path.join(root, f), example_root)
                    files.append(rel_path.replace("\\", "/"))

    files.sort()
    return jsonify(files)


@app.route("/api/example/<path:name>")
def load_example(name):
    path = os.path.join("examples", name)

    if not os.path.exists(path):
        return jsonify({"error": "Example not found"}), 404

    with open(path, "r", encoding="utf-8") as f:
        code = f.read()

    return jsonify({"code": code, "filename": name})


@app.route("/api/file/create", methods=["POST"])
def create_file():
    data = request.json or {}
    filename = data.get("filename", "").strip()
    code = data.get("code", "")
    folder = data.get("folder", "user_tests").strip()

    if not filename:
        return jsonify({"error": "Filename is required"}), 400

    if not filename.endswith(".c"):
        filename += ".c"

    filename = os.path.basename(filename)

    if folder:
        safe_folder = os.path.normpath(folder).replace("..", "").strip("/\\")
        target_dir = os.path.join("examples", safe_folder)
    else:
        target_dir = os.path.join("examples", "user_tests")

    os.makedirs(target_dir, exist_ok=True)
    full_path = os.path.join(target_dir, filename)

    default_template = """int main() {
    // Write your C code here
    return 0;
}
"""
    file_content = code if code is not None and code != "" else default_template

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(file_content)

    rel_name = os.path.relpath(full_path, "examples").replace("\\", "/")
    return jsonify({
        "success": True,
        "filename": rel_name,
        "code": file_content,
        "message": f"Created {rel_name}"
    })


@app.route("/api/file/save", methods=["POST"])
def save_file():
    data = request.json or {}
    filename = data.get("filename", "").strip()
    code = data.get("code", "")

    if not filename:
        return jsonify({"error": "Filename is required"}), 400

    safe_rel = os.path.normpath(filename).replace("..", "").strip("/\\")
    full_path = os.path.join("examples", safe_rel)

    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(code)

    return jsonify({"success": True, "message": f"Saved {safe_rel}"})


def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")


if __name__ == "__main__":
    threading.Timer(1.0, open_browser).start()
    app.run(debug=True, use_reloader=False)