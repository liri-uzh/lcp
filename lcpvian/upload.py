"""
upload.py: /create and /upload endpoints, for creating new db schemata and for
importing data into them. These endpoints can also be polled, which returns
status information about the current task
"""

import base64
import hashlib
import json
import os

import shutil
import traceback

from datetime import datetime, timedelta
import tarfile
from typing import cast, Any, Callable
from uuid import uuid4
from zipfile import ZipFile, is_zipfile

from aiohttp import web, BodyPartReader
from py7zr import SevenZipFile, is_7zfile
from rq.job import Job

from .authenticate import Authentication
from .ddl_gen import generate_ddl
from .dqd_parser import convert
from .typed import JSON
from .utils import (
    _sanitize_corpus_name,
    _row_to_value,
    _sanitize_header,
    _load_top_module_file,
)

lcpcli = _load_top_module_file(
    "lcpcli", os.path.join("lcpcli", "lcpcli", "__init__.py")
)

VALID_EXTENSIONS = ("vrt", "csv", "tsv")
COMPRESSED_EXTENTIONS = ("zip", "tar", "tar.gz", "tar.xz", "7z")
MEDIA_EXTENSIONS = ("mp3", "mp4", "wav", "ogg", "png", "jpg", "jpeg", "bmp")
UPLOADS_PATH = os.getenv("TEMP_UPLOADS_PATH", "uploads")
UPLOAD_TTL = os.getenv("QUERY_TTL", 5000)


async def _create_status_check(request: web.Request, job_id: str) -> web.Response:
    """
    What to do when user check status on an upload job
    """
    qs = request.app["query_service"]
    job: Job | None = qs.get(job_id)
    if not job:
        ret = {"job": job_id, "status": "failed", "error": "Job not found."}
        return web.json_response(ret)
    status = job.get_status(refresh=True)
    msg = f"""Please wait: corpus processing in progress..."""
    # project = job.kwargs["project"]
    if status == "failed":
        res = job.latest_result()
        msg = "Error"
        if res:
            msg += f": {res.exc_string}"
    elif status == "finished":
        msg = f"""Template validated successfully"""
    kwargs: dict = cast(dict, job.kwargs)
    ret = {
        "job": job.id,
        "status": status,
        "info": msg,
        "project": kwargs["project"],
        "project_name": kwargs["project_name"],
        "corpus_name": kwargs["corpus_name"],
        "target": f"/create?job={job_id}",
    }
    return web.json_response(ret)


async def _status_check(request: web.Request, job_id: str) -> web.Response:
    """
    What to do when user check status on an upload job
    """
    qs = request.app["query_service"]
    job = qs.get(job_id)
    project = job.args[0]
    progfile = os.path.join(UPLOADS_PATH, project, ".progress.txt")
    progress = _get_progress(progfile)

    if not job:
        ret = {"job": job_id, "status": "failed", "error": "Job not found."}
        return web.json_response(ret)
    status = job.get_status(refresh=True)
    msg = f"""Please wait: corpus processing in progress..."""

    if status == "failed":
        msg = f"Error: {str(job.latest_result().exc_string)}"
    elif status == "finished":
        msg = f"""
        Upload is complete. You should be able to see your
        corpus in the web app. You may need to grant permission to
        other users if you want to allow them to access it.
        """
    ret = {
        "job": job.id,
        "status": status,
        "info": " ".join(msg.split()),
        "project": project,
    }
    if job.result:
        ret["corpus_id"] = job.result[0]
    if progress:
        ret["progress"] = "/".join(str(x) for x in progress)
    return web.json_response(ret)


def _get_progress(progfile: str) -> tuple[int, int, str, str] | None:
    """
    Attempt to get progress from saved file
    """
    if not os.path.isfile(progfile):
        return None
    msg = "Importing corpus"
    unit = "byte"
    extra = ":progress:"
    with open(progfile, "r") as fo:
        data = fo.read()
    if "\nSetting constraints..." in data:
        msg = "Indexing corpus"
        unit = "task"
        extra = ":extras:"
    if "\nComputing prepared segments" in data:
        msg = "Optimising corpus"
        unit = "task"
        extra = ":extras:"
    bits = [
        i.strip(":").strip().split(":")
        for i in data.splitlines()
        if i.startswith(":progress:") and extra in i
    ]
    if not bits:
        return None
    done_bytes = sum([int(i[1]) for i in bits])
    total = int(bits[-1][2])
    done_bytes = min(done_bytes, total)
    return (done_bytes, total, msg, unit)


def _check_dqd(template: dict) -> bool:
    print("check_dqd", template)
    if "meta" not in template or "sample_query" not in template["meta"]:
        return True
    success: bool
    try:
        print("before convering")
        json_q = convert(template["meta"]["sample_query"], template)
        print("after convering", json_q)
        success = True
    except:
        success = False
    return success


def _ensure_partitioned0(data, path: str) -> None:
    """
    In case the user didn't call word.csv word0.csv
    """
    srcs = [os.path.join(path, "fts_vector.csv"), os.path.join(path, "fts_vector.tsv")]
    for layer in ("token", "segment"):
        lay = data["firstClass"][layer]
        srcs.append(os.path.join(path, lay.lower() + ".csv"))
        srcs.append(os.path.join(path, lay.lower() + ".tsv"))
    for src in srcs:
        if os.path.isfile(src):
            dest = src.replace(".csv", "0.csv")
            dest = dest.replace(".tsv", "0.tsv")
            os.rename(src, dest)
            print(f"Moved: {src}->{dest}")


def _correct_doc(data, path: str) -> None:
    """
    Fix incorrect JSON formatting...
    todo: remove this when fixed upstream
    """
    doc = data["firstClass"]["document"]
    docpath = os.path.join(path, f"{doc}.csv".lower())
    if not os.path.exists(docpath):
        docpath = os.path.join(path, f"{doc}.tsv".lower())
    with open(docpath, "r") as fo:
        data = fo.read()
    data = data.replace("\t'{", "\t{").replace("}'\n", "}\n")
    with open(docpath, "w") as fo:
        fo.write(data)


def _parse_tus_metadata(header_value):
    if not header_value:
        return {}
    metadata = {}
    for pair in header_value.split(","):
        key, encoded_value = pair.split(" ", 1)
        metadata[key] = base64.b64decode(encoded_value).decode()
    return metadata


async def _validate_upload_request(
    request: web.Request, upload_id: str = ""
) -> tuple[bool, dict]:
    headers = request.headers
    authenticator: Authentication = request.app["auth_class"](request.app)
    status = await authenticator.check_api_key(request)

    metadata = _parse_tus_metadata(request.headers.get("Upload-Metadata", ""))
    payload = {k: v for k, v in metadata.items()}

    filename = metadata.get("filename", "")
    job_id = metadata.get("job_id", "")
    if not job_id:
        try:
            upload_info = _get_upload_for_id(request, upload_id)
            payload.update(upload_info)
            job_id = upload_info.get("job_id", "")
            filename = upload_info.get("filename", "")
        except Exception as e:
            return False, {"error": f"Unauthorized: {str(e)}"}

    job: Job
    try:
        payload["job_id"] = job_id
        job = Job.fetch(job_id, connection=request.app["redis"])
        kwargs: dict = cast(dict, job.kwargs)
        payload["cpath"] = kwargs["path"]
        username = kwargs["user"]
        payload["username"] = username
        payload.update({p: kwargs[p] for p in ("room", "project", "project_name")})
        user_acc = cast(dict[str, dict[Any, Any] | str], status["account"])
        assert username == user_acc["email"], PermissionError("Invalid user ID")
    except Exception as e:
        return False, {"error": f"Unauthorized: {str(e)}"}

    if int(headers.get("Upload-Length", 0)) > 100_000_000_000:  # 100GB limit
        return False, {"error": "File too large"}

    payload["filename"] = filename
    complete_files = job.meta.get("complete_files") or {}
    complete_files.setdefault(filename, False)
    job.meta["complete_files"] = complete_files
    job.save_meta()

    return True, payload


def _get_upload_for_id(request: web.Request, upload_id) -> dict:
    connection = request.app["redis"]
    key = f"uploads::{upload_id}"
    try:
        upload = json.loads(connection.get(key))
        connection.expire(key, UPLOAD_TTL)
        return upload
    except Exception as e:
        print(f"Error with upload: {str(e)}")
    return {}


def _set_upload_for_id(request: web.Request, upload_id: str, upload: dict):
    connection = request.app["redis"]
    key = f"uploads::{upload_id}"
    connection.set(key, json.dumps(upload))
    connection.expire(key, UPLOAD_TTL)


async def _complete_upload(request: web.Request, payload: dict) -> dict[str, str | int]:
    cpath = payload.get("cpath", "")
    authenticator: Authentication = request.app["auth_class"](request.app)
    user_data = await authenticator.user_details(request)

    ziptar: list[tuple[str, Callable, Callable, str, str]] = [
        (".zip", is_zipfile, ZipFile, "namelist", "r"),
        (".tar", tarfile.is_tarfile, tarfile.open, "getnames", "r"),
        (".tar.gz", tarfile.is_tarfile, tarfile.open, "getnames", "r:gz"),
        (".tar.xz", tarfile.is_tarfile, tarfile.open, "getnames", "r"),
        (".7z", is_7zfile, SevenZipFile, "getnames", "r"),
    ]

    upload_path = os.path.join(UPLOADS_PATH, cpath)
    for file in os.listdir(upload_path):
        path = os.path.join(upload_path, file)
        for ext, check, opener, method, mode in ziptar:
            if path.endswith(ext) and check(path):
                _extract_file(path, cpath, ext, opener, method, mode)
            elif path.endswith(ext) and not check(path):
                print(f"Something wrong with {path}. Ignoring...")
                os.remove(path)
                fp = os.path.basename(path)
                return {"status": "failed", "error": f"Problem uncompressing {fp}"}

    if payload.get("media"):
        job = Job.fetch(payload.get("job_id") or "", connection=request.app["redis"])
        project_id = payload.get("project")
        project_name = payload.get("project_name")
        ret = {
            "status": "finished",
            "job": job.id,
            "project": str(project_id),
            "project_name": project_name,
        }
        try:
            corpus = {}
            corpus_super = payload.get("corpus_super")
            is_super_admin = cast(dict, user_data["user"]).get("superAdmin")
            if corpus_super and is_super_admin:
                corpus = request.app["config"][str(corpus_super)]
            else:
                insert_job = Job.fetch(
                    job.meta["insert_job"], connection=request.app["redis"]
                )
                corpus = cast(dict, _row_to_value(insert_job.result))
            ret["corpus_name"] = corpus.get("name", "")
            _move_media_files(cpath, corpus.get("schema_path", ""))
        except Exception as err:
            ret["status"] = "failed"
            ret["error"] = f"Something went wrong with uploading the media files: {err}"
        return ret

    template = os.path.join(upload_path, "_data.json")
    with open(template, "r") as fo:
        data = json.load(fo)
        data = data["template"]
        _ensure_partitioned0(data, upload_path)
        _correct_doc(data, upload_path)

    return_data: dict[str, str | int] = {}

    qs = request.app["query_service"]
    kwa = dict(
        gui=False,
        user_data=user_data,
        delimiter=request.rel_url.query.get("delimiter", ""),
        quote=request.rel_url.query.get("quote", ""),
        escape=request.rel_url.query.get("escape", ""),
    )

    print(f"Uploading data to database: {cpath}")
    username = payload.get("username", "")
    room = payload.get("room", "")
    insert_job = qs.insert_data(username, cpath, room, **kwa)
    job = Job.fetch(payload.get("job_id", ""), connection=request.app["redis"])
    job.meta["complete_files"] = {}  # we're done with the DB files
    job.meta["insert_job"] = insert_job.id
    job.save()
    short_url = str(request.url).split("?", 1)[0]
    suggest_url = f"{short_url}?job={insert_job.id}"
    info = f"Data insertion into the databse has begun. If you want to check the status, POST to:  {suggest_url}"
    return_data.update(
        {
            "status": "started",
            "job": insert_job.id,
            "project": payload.get("project", ""),
            "project_name": payload.get("project_name", ""),
            "info": info,
            "target": f"/monitor_db_insert?job={insert_job.id}",
        }
    )

    return return_data


async def _complete_file(request: web.Request, payload: dict) -> dict[str, str | int]:
    filename = payload.get("filename", "")
    job = Job.fetch(payload.get("job_id", ""), connection=request.app["redis"])
    complete_files = job.meta.get("complete_files") or {}
    complete_files[filename] = True
    job.save_meta()

    files_md5 = hashlib.md5(
        "".join(sorted(fn for fn in complete_files)).encode()
    ).hexdigest()
    if str(files_md5) == payload.get("files_md5"):
        return await _complete_upload(request, payload)
    return {}


# POST /upload
async def create_upload(request: web.Request) -> web.Response:
    is_valid, payload = await _validate_upload_request(request)
    if not is_valid:
        return web.json_response({"error": payload.get("error", "")}, status=403)

    upload_id = str(uuid4())
    directory = os.path.join(UPLOADS_PATH, payload.get("cpath", ""))
    os.makedirs(directory, exist_ok=True)
    upload_path = os.path.join(directory, payload.get("filename", ""))
    upload_info = {k: v for k, v in payload.items()}
    upload_info.update(
        {
            "offset": 0,
            "length": int(request.headers.get("Upload-Length", 0)),
            "path": upload_path,
        }
    )
    _set_upload_for_id(
        request,
        upload_id,
        upload_info,
    )
    open(upload_path, "wb").close()  # Create empty file

    response = web.Response(
        status=201,
        headers={"Location": f"/upload/{upload_id}"},
    )
    return response


# PATCH /upload/<upload_id>
async def upload_chunk(request: web.Request) -> web.Response:
    upload_id = request.match_info["upload_id"]
    is_valid, payload = await _validate_upload_request(request, upload_id)
    if not is_valid:
        return web.json_response({"error": payload.get("error", "")}, status=403)

    upload = _get_upload_for_id(request, upload_id)
    if not upload:
        return web.Response(status=404)

    offset = int(request.headers.get("Upload-Offset", 0))
    if offset != upload["offset"]:
        return web.Response(status=409)  # Offset mismatch

    chunk = await request.read()
    with open(upload["path"], "ab") as f:
        f.write(chunk)
    upload["offset"] += len(chunk)

    headers = {"Upload-Offset": str(upload["offset"])}

    # --- DETECT LAST CHUNK ---
    if upload.get("length") is not None and upload["offset"] == upload["length"]:
        print(f"✅ Last chunk received for {upload_id}")
        response = await _complete_file(request, payload)
        if response and response.get("status") not in ("started", "finished"):
            return web.json_response({"error": response.get("error", "")}, status=500)
        headers.update(
            {
                f"X-{_sanitize_header(k)}": _sanitize_header(str(v))
                for k, v in response.items()
            }
        )

    _set_upload_for_id(request, upload_id, upload)

    return web.Response(
        status=204,
        headers=headers,
    )


# HEAD /upload/<upload_id>
async def upload_info(request):
    upload_id = request.match_info["upload_id"]
    is_valid, payload = await _validate_upload_request(request, upload_id)
    if not is_valid:
        return web.json_response({"error": payload.get("error", "")}, status=403)

    upload = _get_upload_for_id(request, upload_id)
    if not upload:
        return web.Response(status=404)

    return web.Response(
        status=200,
        headers={
            "Upload-Offset": str(upload["offset"]),
            "Upload-Length": str(upload["length"]),
        },
    )


async def monitor_db_insert(request: web.Request) -> web.Response:
    """
    Monitor upload of data to database
    """
    job_id = request.rel_url.query["job"]

    return await _status_check(request, job_id)


async def _save_file(path: str, bit: BodyPartReader, has_file: bool) -> bool:
    """
    Helper to save file sent by FE to server
    """
    dirname = os.path.dirname(path)
    if not os.path.exists(dirname):
        os.mkdir(dirname)
    with open(path, "ba") as f:
        while True:
            chunk = await bit.read_chunk()
            if not chunk:
                break
            f.write(chunk)
            has_file = True
    return has_file


def _extract_file(
    # bit: BodyPartReader,
    path: str,
    cpath: str,
    ext: str,
    opener: Callable,
    method: str,
    mode: str,
) -> None:
    # print(f"Extracting {ext} file: {bit.filename}")
    with opener(path, mode) as compressed:
        for f in getattr(compressed, method)():
            basef = os.path.basename(str(f))
            if (
                not str(f).endswith(VALID_EXTENSIONS + MEDIA_EXTENSIONS)
                and not f == f"media{os.sep}"
            ):
                continue
            just_f = os.path.join(UPLOADS_PATH, cpath, basef)
            dest = os.path.join(UPLOADS_PATH, cpath)
            print(f"Uncompressing {basef}")
            if ext != ".7z":
                compressed.extract(f, dest)
            else:
                compressed.extract(dest, [f])
            try:
                if str(f).endswith(VALID_EXTENSIONS):
                    # does not apply to media files
                    os.rename(os.path.join(dest, str(f)), just_f)
            except Exception as err:
                print(f"Warning: {err}")
                pass
            print(f"Extracted: {basef}")
    print(f"Extracting {ext} done!")
    os.remove(path)  # todo: should we do this now?
    print(f"Deleted: {path}")


def _move_media_files(cpath: str, corpus_dir: str) -> None:
    print("Moving media files")
    media_path = os.environ.get("UPLOAD_MEDIA_PATH", "media")
    dest_path = os.path.join(media_path, corpus_dir)
    if not os.path.exists(dest_path):
        os.makedirs(dest_path)
    source_path = os.path.join(UPLOADS_PATH, cpath)
    for f in os.listdir(source_path):
        print("File in cpath", f)
        if not str(f).endswith(MEDIA_EXTENSIONS):
            continue
        basename = os.path.basename(f)
        shutil.move(
            os.path.join(source_path, basename), os.path.join(dest_path, basename)
        )


async def make_schema(request: web.Request) -> web.Response:
    """
    What happens when a user goes to /create and POSTs JSON
    """
    if str(request.headers.get("X-LCPCLI-Version")) != str(lcpcli.__version__):
        error = {
            "status": "failed",
            "message": f"Invalid version of LCPCLI -- please use version {lcpcli.__version__}",
        }
        return web.json_response(error)

    authenticator: Authentication = request.app["auth_class"](request.app)

    exists = request.rel_url.query.get("job")
    if exists:
        return await _create_status_check(request, exists)

    request_data = await request.json()

    template = request_data["template"]
    if not _check_dqd(template):
        error = {"status": "failed", "message": "Invalid sample query"}
        return web.json_response(error)

    room = request_data.get("room", None)
    projects = request_data.get("projects")
    special = {"lcp", "all"}
    project = next(i for i in projects if i not in special)

    today = datetime.today()
    later = today + timedelta(weeks=52, days=2)

    try:
        key = request.headers.get("X-API-Key")
        assert isinstance(key, str), "Missing API key"
        secret = request.headers.get("X-API-Secret")
        assert isinstance(secret, str), "Missing API key secret"
        status = await authenticator.check_api_key(request)
        assert "account" in status, "No account in status"
    except Exception as err:
        tb = traceback.format_exc()
        msg = f"Could not verify user: bad crendentials?"
        print(msg)
        error = {"traceback": tb, "status": "failed"}
        # logging.error(msg, extra=error)
        error["message"] = f"{msg} -- {err}"
        return web.json_response(error)

    user_acc = cast(dict[str, dict[Any, Any] | str], status["account"])
    user_id: str = cast(str, user_acc["email"])
    existing_project = cast(dict[str, JSON], status.get("profile", {}))

    ids = (existing_project.get("id"), existing_project.get("title"))

    if project and project not in ids:
        start = template["meta"].get("startDate", today.strftime("%Y-%m-%d"))
        finish = template["meta"].get("finishDate", later.strftime("%Y-%m-%d"))
        uacc: dict[str, Any] = cast(dict[str, Any], user_acc.get("account", {}))
        uname: str = cast(str, uacc.get("displayName", ""))
        profile: dict[str, str] = {
            "title": f"{uname}: private group",
            "unit": uacc.get("homeOrganization", ""),
            "startDate": start,
            "finishDate": finish,
        }

        try:
            existing_project = await authenticator.project_create(request, profile)
            if existing_project.get("status", True) is not False:
                proj = json.dumps(existing_project, indent=4)
                msg = f"New project created:\n{proj}"
                print(msg)
                # logging.info(msg, extra=existing_project)
        except Exception as err:
            tb = traceback.format_exc()
            msg = f"Could not create project: {project} already exists?"
            print(msg)
            error = {"traceback": tb, "status": "failed"}
            # logging.error(msg, extra=error)
            error["message"] = f"{msg} -- {err}"
            return web.json_response(error)

    # corpus_folder = str(uuid4())
    if existing_project.get("status", True) is False:
        error = {
            "status": "failed",
            "message": f"Could not get project",
        }
        return web.json_response(error)

    proj_id = cast(str, existing_project["id"])

    corpus_name = _sanitize_corpus_name(template["meta"]["name"])

    sames = {
        cid: i
        for cid, i in request.app["config"].items()
        if "meta" in i
        and _sanitize_corpus_name(i["meta"]["name"]) == corpus_name
        and proj_id in i.get("projects", [])  # only corpora from the same project
        and i.get("enabled")
    }

    if sames and not request_data.get("overwrite"):
        return web.json_response(
            {
                "status": "failed",
                "project": proj_id,
                "user_id": user_id,
                "error": f"A corpus named '{corpus_name}' already exists in the collection '{existing_project.get('title', '')}'.",
                "corpus_id": next(s for s in sames),
            }
        )

    corpus_version = (
        max(int(x["current_version"]) for x in sames.values()) if sames else 0
    ) + 1
    template["meta"] = template.get("meta", {})
    template["meta"]["version"] = corpus_version

    # Temporary schema name
    schema_name = str(uuid4())

    template["projects"] = [proj_id]
    template["project"] = proj_id
    template["schema_name"] = schema_name

    try:
        no_index: list[list[str]] = cast(
            list[list[str]], request_data.get("no_index", [])
        )
        n_batches = request_data.get("n_batches", 10)
        pieces = generate_ddl(template, proj_id, corpus_version, no_index, n_batches)
        pieces["template"] = template
    except Exception as err:
        tb = traceback.format_exc()
        msg = f"Could not create schema:"
        error = {"traceback": tb, "status": "failed"}
        # logging.error(msg, extra=error)
        error["message"] = f"{msg} -- {err}"
        print(error["message"])
        return web.json_response(error)

    corpus_path = os.path.join(proj_id, schema_name)

    directory = os.path.join(UPLOADS_PATH, corpus_path)
    if os.path.exists(directory):
        shutil.rmtree(directory, ignore_errors=True)
    os.makedirs(directory)

    # pieces["drops"] = drops
    with open(os.path.join(directory, "_data.json"), "w") as fo:
        json.dump(pieces, fo)

    job = request.app["query_service"].create(
        pieces["create"],
        project=proj_id,
        path=corpus_path,
        schema_name=schema_name,
        user=user_id,
        room=room,
        # drops=drops,
        project_name=existing_project["title"],
        corpus_name=corpus_name,
    )
    return web.json_response(
        {
            "status": "started",
            "job": job.id,
            "project": proj_id,
            "schema": schema_name,
            "path": corpus_path,
            "target": f"/create?job={job.id}",
            "user_id": user_id,
        }
    )
