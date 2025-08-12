"""
upload.py: /create and /upload endpoints, for creating new db schemata and for
importing data into them. These endpoints can also be polled, which returns
status information about the current task
"""

import json
import os

import shutil
import traceback

from datetime import datetime, timedelta
from tarfile import TarFile, is_tarfile
from typing import cast, Any
from uuid import uuid4
from zipfile import ZipFile, is_zipfile

from aiohttp import web, BodyPartReader
from py7zr import SevenZipFile, is_7zfile
from rq.job import Job

from .authenticate import Authentication
from .ddl_gen import generate_ddl
from .dqd_parser import convert
from .typed import JSON
from .utils import _sanitize_corpus_name, _row_to_value


VALID_EXTENSIONS = ("vrt", "csv", "tsv")
COMPRESSED_EXTENTIONS = ("zip", "tar", "tar.gz", "tar.xz", "7z")
MEDIA_EXTENSIONS = ("mp3", "mp4", "wav", "ogg", "png", "jpg", "jpeg", "bmp")
UPLOADS_PATH = os.getenv("TEMP_UPLOADS_PATH", "uploads")


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


def _ensure_partitioned0(path: str) -> None:
    """
    In case the user didn't call word.csv word0.csv
    """
    template = os.path.join(path, "_data.json")
    with open(template, "r") as fo:
        data = json.load(fo)
        data = data["template"]
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


def _correct_doc(path: str) -> None:
    """
    Fix incorrect JSON formatting...
    todo: remove this when fixed upstream
    """
    template = os.path.join(path, "_data.json")
    with open(template, "r") as fo:
        data = json.load(fo)
        data = data["template"]
    doc = data["firstClass"]["document"]
    docpath = os.path.join(path, f"{doc}.csv".lower())
    if not os.path.exists(docpath):
        docpath = os.path.join(path, f"{doc}.tsv".lower())
    with open(docpath, "r") as fo:
        data = fo.read()
    data = data.replace("\t'{", "\t{").replace("}'\n", "}\n")
    with open(docpath, "w") as fo:
        fo.write(data)


async def upload(request: web.Request) -> web.Response:
    """
    Handle upload of data (save files, insert into db)
    """
    authenticator: Authentication = request.app["auth_class"](request.app)

    url = request.url
    job_id = request.rel_url.query["job"]
    checking = request.rel_url.query.get("check")
    if checking:
        return await _status_check(request, job_id)

    user_data = await authenticator.user_details(request)
    if not user_data:
        raise PermissionError("Could not authenticate the user")

    gui_mode = request.rel_url.query.get("gui", False)

    job = Job.fetch(job_id, connection=request.app["redis"])
    # schema_name: str = cast(str, job.args[1])
    kwargs: dict = cast(dict, job.kwargs)
    project_id = kwargs["project"]
    username = kwargs["user"]
    room = kwargs["room"]
    project_name = kwargs["project_name"]
    corpus_name = kwargs["corpus_name"]
    cpath = kwargs["path"]

    ziptar = [
        (".zip", is_zipfile, ZipFile, "namelist"),
        (".tar", is_tarfile, TarFile, "getnames"),
        (".tar.gz", is_tarfile, TarFile, "getnames"),
        (".tar.xz", is_tarfile, TarFile, "getnames"),
        (".7z", is_7zfile, SevenZipFile, "getnames"),
    ]

    # username = request.rel_url.query.get("user_id", "")
    # room = request.rel_url.query.get("room", None)

    if not project_id:
        return web.json_response({"status": "failed"})

    data = await request.multipart()
    has_file = False
    bit: BodyPartReader
    async for bit in data:
        if not isinstance(bit.filename, str):
            continue
        if not bit.filename.endswith(
            VALID_EXTENSIONS + COMPRESSED_EXTENTIONS + MEDIA_EXTENSIONS
        ):
            continue
        ext = os.path.splitext(bit.filename)[-1]
        path = os.path.join(UPLOADS_PATH, cpath, bit.filename)

        has_file = await _save_file(path, bit, has_file)

        for ext, check, opener, method in ziptar:
            if path.endswith(ext) and check(path):
                _extract_file(bit, path, cpath, ext, opener, method)
            elif path.endswith(ext) and not check(path):
                print(f"Something wrong with {path}. Ignoring...")
                os.remove(path)
                fp = os.path.basename(path)
                ret = {"status": "failed", "msg": f"Problem uncompressing {fp}"}
                return web.json_response(ret)

    if request.rel_url.query.get("media"):
        ret = {
            "status": "finished",
            "job": job.id,
            "project": str(project_id),
            "project_name": project_name,
            "corpus_name": corpus_name,
        }
        try:
            upload_job = Job.fetch(
                job.meta["upload_job"], connection=request.app["redis"]
            )
            corpus_entry = _row_to_value(upload_job.result)
            # Need a better method than that - move to authenticate
            # ud = cast(dict, user_data)
            # user_projects: set = {p.get("id") for p in ud["publicProfiles"]}
            # user_projects.update(
            #     {p.get("id") for sb in ud["subscription"] for sbs in sb for p in sbs}
            # )
            # assert corpus_entry.get("project") in user_projects, PermissionError(
            #     "User is not authorized to upload files to this project"
            # )
            _move_media_files(cpath, corpus_entry.get("schema_path", ""))
            # shutil.rmtree(cpath)  # todo: should we do this?
        except Exception as err:
            ret["status"] = "failed"
            ret["error"] = f"Something went wrong with uploading the media files: {err}"
        return web.json_response(ret)

    _ensure_partitioned0(os.path.join(UPLOADS_PATH, cpath))
    _correct_doc(os.path.join(UPLOADS_PATH, cpath))

    return_data: dict[str, str | int] = {}
    if not has_file:
        msg = "No file sent?"
        return_data.update({"status": "failed", "info": msg})
        return web.json_response(return_data)

    qs = request.app["query_service"]
    kwa = dict(
        gui=gui_mode,
        user_data=user_data,
        delimiter=request.rel_url.query.get("delimiter", ""),
        quote=request.rel_url.query.get("quote", ""),
        escape=request.rel_url.query.get("escape", ""),
    )
    path = os.path.join(UPLOADS_PATH, cpath)
    print(f"Uploading data to database: {cpath}")
    upload_job = qs.upload(username, cpath, room, **kwa)
    job.meta["upload_job"] = upload_job.id
    job.save()
    short_url = str(url).split("?", 1)[0]
    suggest_url = f"{short_url}?job={upload_job.id}"
    info = f"""Data upload has begun. If you want to check the status, POST to:
        {suggest_url}
    """
    return_data.update(
        {
            "status": "started",
            "job": upload_job.id,
            "project": str(project_id),
            "project_name": project_name,
            "info": info,
            "target": f"/upload?job={upload_job.id}",
        }
    )

    return web.json_response(return_data)


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
    bit: BodyPartReader, path: str, cpath: str, ext: str, opener: type, method: str
) -> None:
    print(f"Extracting {ext} file: {bit.filename}")
    with opener(path, "r") as compressed:
        for f in getattr(compressed, method)():
            basef = os.path.basename(str(f))
            if not str(f).endswith(VALID_EXTENSIONS):
                continue
            just_f = os.path.join(UPLOADS_PATH, cpath, basef)
            dest = os.path.join(UPLOADS_PATH, cpath)
            print(f"Uncompressing {basef}")
            if ext != ".7z":
                compressed.extract(f, dest)
            else:
                compressed.extract(dest, [f])
            try:
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
    media_path = os.environ.get("UPLOAD_MEDIA_PATH", os.path.join("media"))
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
        # os.rename(
        #     os.path.join(source_path, basename), os.path.join(dest_path, basename)
        # )


async def make_schema(request: web.Request) -> web.Response:
    """
    What happens when a user goes to /create and POSTs JSON
    """
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
    # corpus_version = template["meta"]["version"]
    # below we add a random suffix to the corpus name.
    # suffix of the name has 1/65536 chance of collision,
    # which is on the borderline of being too high in prod.
    # becomes 1/4.3b chance if we use [0] instead of [1]
    # but the schema name gets noticeably uglier, so ...

    #  suffix = corpus_folder.split("-", 2)[1]
    # suffix = re.sub(r"[^a-zA-Z0-9]", "", proj_id)
    # version_n = re.sub(r"[^0-9]", "", str(corpus_version))

    # schema_name = f"{corpus_name}__{suffix}_{version_n}"

    sames = [
        i
        for i in request.app["config"].values()
        if "meta" in i
        and _sanitize_corpus_name(i["meta"]["name"]) == corpus_name
        and proj_id in i.get("projects", [])  # only corpora from the same project
        # and str(i["meta"]["version"]) == str(corpus_version)
    ]

    corpus_version = (max(int(x["current_version"]) for x in sames) if sames else 0) + 1
    # schema_name = f"{corpus_name.lower()}__{suffix}_{corpus_version}"
    template["meta"] = template.get("meta", {})
    template["meta"]["version"] = corpus_version

    # todo: is this the right approach?
    # cv = f"'{corpus_version}'" if isinstance(corpus_version, str) else corpus_version
    # delete = f"DELETE FROM main.corpus WHERE name = '{template['meta']['name']}' AND current_version < {cv};"
    # drops.append(delete)
    # deletes = [
    #     f"DELETE FROM main.corpus WHERE corpus_id = {int(i)};"
    #     for i in set(x["corpus_id"] for x in sames if "corpus_id" in x)
    # ]
    # drops += deletes

    # Temporary schema name
    schema_name = str(uuid4())

    template["projects"] = [proj_id]
    template["project"] = proj_id
    template["schema_name"] = schema_name

    try:
        no_index: list[list[str]] = cast(
            list[list[str]], request_data.get("no_index", [])
        )
        pieces = generate_ddl(template, proj_id, corpus_version, no_index)
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
