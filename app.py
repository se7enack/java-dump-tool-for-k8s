import datetime
import tempfile
import os
import uuid
import threading
import time

from flask import Flask, render_template, request, send_file, jsonify
from kubernetes import client, config
from kubernetes.stream import stream

app = Flask(__name__)

config.load_kube_config()
v1 = client.CoreV1Api()

JFR_JOBS = {}

@app.route("/", methods=["GET"])
def index():
    namespace = request.args.get("namespace", "default")
    namespaces = [ns.metadata.name for ns in v1.list_namespace().items]
    pods = v1.list_namespaced_pod(namespace).items

    return render_template(
        "index.html",
        pods=pods,
        namespace=namespace,
        namespaces=namespaces,
    )

@app.route("/dump", methods=["POST"])
def dump():
    pod = request.form["pod"]
    namespace = request.form["namespace"]
    container = request.form["container"]
    dump_type = request.form.get("dump_type", "thread")

    ts = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    pid = "1"

    if dump_type == "thread":
        output_path = f"/tmp/thread-{ts}.txt"
        exec_cmd = ["sh", "-c", f"jcmd {pid} Thread.print > {output_path}"]
        filename = f"{pod}-{namespace}-{ts}-thread.txt"
        mimetype = "text/plain"

    elif dump_type == "heap":
        output_path = f"/tmp/heap-{ts}.hprof"
        exec_cmd = ["sh", "-c", f"jcmd {pid} GC.heap_dump {output_path}"]
        filename = f"{pod}-{namespace}-{ts}-heap.hprof"
        mimetype = "application/octet-stream"

    else:
        return "Invalid dump type", 400

    stream(
        v1.connect_get_namespaced_pod_exec,
        pod,
        namespace,
        container=container,
        command=exec_cmd,
        stdout=True,
        stderr=True,
        stdin=False,
        tty=False,
    )

    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_file_path = tmp_file.name

        file_stream = stream(
            v1.connect_get_namespaced_pod_exec,
            pod,
            namespace,
            container=container,
            command=["cat", output_path],
            stdout=True,
            stderr=True,
            stdin=False,
            tty=False,
            _preload_content=False,
        )

        while file_stream.is_open():
            file_stream.update(timeout=5)

            if file_stream.peek_stdout():
                out = file_stream.read_stdout()
                if isinstance(out, str):
                    out = out.encode("utf-8")
                tmp_file.write(out)

            if file_stream.peek_stderr():
                err = file_stream.read_stderr()
                if err:
                    print(f"{dump_type} stderr:", err)

        file_stream.close()
        tmp_file.flush()

    stream(
        v1.connect_get_namespaced_pod_exec,
        pod,
        namespace,
        container=container,
        command=["rm", "-f", output_path],
        stdout=True,
        stderr=True,
        stdin=False,
        tty=False,
    )

    response = send_file(
        tmp_file_path,
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename,
    )

    @response.call_on_close
    def cleanup_temp_file():
        try:
            os.remove(tmp_file_path)
        except Exception:
            pass

    return response

@app.route("/jfr/start", methods=["POST"])
def jfr_start():
    pod = request.form["pod"]
    namespace = request.form["namespace"]
    container = request.form["container"]
    duration = int(request.form["duration"])

    job_id = str(uuid.uuid4())
    ts = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    jfr_path = f"/tmp/recording-{ts}.jfr"
    pid = "1"

    stream(
        v1.connect_get_namespaced_pod_exec,
        pod,
        namespace,
        container=container,
        command=[
            "sh",
            "-c",
            f"jcmd {pid} JFR.start duration={duration}s filename={jfr_path}",
        ],
        stdout=True,
        stderr=True,
        stdin=False,
        tty=False,
    )

    JFR_JOBS[job_id] = {
        "pod": pod,
        "namespace": namespace,
        "container": container,
        "path": jfr_path,
        "ready_at": time.time() + duration,
        "filename": f"{pod}-{namespace}-{ts}-{duration}s.jfr",
    }

    return jsonify({"job_id": job_id, "duration": duration})

@app.route("/jfr/status/<job_id>")
def jfr_status(job_id):
    job = JFR_JOBS.get(job_id)
    if not job:
        return jsonify({"status": "missing"}), 404
    remaining = int(job["ready_at"] - time.time())
    if remaining <= 0:
        return jsonify({"status": "ready", "remaining": 0})
    return jsonify({"status": "recording", "remaining": remaining})

@app.route("/jfr/download/<job_id>")
def jfr_download(job_id):
    job = JFR_JOBS.pop(job_id, None)
    if not job:
        return "Not found", 404

    data = stream(
        v1.connect_get_namespaced_pod_exec,
        job["pod"],
        job["namespace"],
        container=job["container"],
        command=["cat", job["path"]],
        stdout=True,
        stderr=True,
        stdin=False,
        tty=False,
        _preload_content=True,
    )

    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write(data.encode("utf-8") if isinstance(data, str) else data)

    stream(
        v1.connect_get_namespaced_pod_exec,
        job["pod"],
        job["namespace"],
        container=job["container"],
        command=["rm", "-f", job["path"]],
        stdout=True,
        stderr=True,
        stdin=False,
        tty=False,
    )

    response = send_file(
        tmp_path,
        as_attachment=True,
        download_name=job["filename"],
        mimetype="application/octet-stream",
    )

    @response.call_on_close
    def cleanup():
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    return response

if __name__ == "__main__":
    host = "0.0.0.0" if os.getenv("INSIDE_CONTAINER") else "127.0.0.1"
    app.run(debug=True, use_reloader=True, host=host, port=5001)
