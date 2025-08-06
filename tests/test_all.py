import json
import os
import re

import sqlparse

from aiohttp.test_utils import AioHTTPTestCase
from rq.command import PUBSUB_CHANNEL_TEMPLATE

from lcpvian.dqd_parser import convert as dqd_to_json

# from lcpvian.sock import listen_to_redis
from lcpvian.utils import _determine_language
from lcpvian.abstract_query.create import json_to_sql
from lcpvian.typed import Batch

# this env var must be set before we import anything from .run
os.environ["_TEST"] = "True"

from lcpvian.app import create_app

# from lcpvian.sock import handle_redis_response
from lcpvian.utils import get_segment_meta_script
from lcpvian.abstract_query.utils import SQLCorpus, SQLRef


PUBSUB_CHANNEL = PUBSUB_CHANNEL_TEMPLATE % "query"

SQL_COMMA = re.compile(r"\s+(,|;)")


def sql_norm(s: str) -> str:
    return re.sub(SQL_COMMA, r"\1", s).strip()


class MyAppTestCase(AioHTTPTestCase):
    # async def tearDownAsync(self):
    #    await super().tearDownAsync()
    #    await on_shutdown(self._app)

    async def get_application(self):
        """
        Override the get_app method to return your application.
        """
        app = await create_app(test=True)
        self._app = app

        # pubsub = app["aredis"].pubsub()
        # async with pubsub as p:
        #    await p.subscribe(PUBSUB_CHANNEL)
        #    await handle_redis_response(p, app, test=True)
        #    await p.unsubscribe(PUBSUB_CHANNEL)

        return app

    # async def test_example(self):

    #    async with self.client.request("POST", "/corpora") as resp:
    #        self.assertEqual(resp.status, 200)
    #        conf_data = await resp.json()
    #        self.assertTrue(str(-1) in conf_data["config"])
    #        self.assertTrue("meta" in conf_data["config"][str(1)])
    #        self.assertTrue("schema_path" in conf_data["config"][str(1)])

    # async def test_queries(self):
    #    worker = "python -m lcpvian worker"
    #    app = "python -m lcpvian start"
    #    w = subprocess.Popen(worker, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    #    a = subprocess.Popen(app, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    #    # stdout, stderr = a.communicate()

    async def test_sqlrefs(self):
        """
        Test that the SQLRef generates the proper SQL bits
        """
        self.maxDiff = None
        test_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "test_data")
        names = {
            os.path.splitext(i)[0]
            for i in os.listdir(test_dir)
            if os.path.splitext(i)[0].isnumeric()
        }
        for n in sorted(names):

            base = os.path.join(test_dir, n)

            if not os.path.exists(base + ".refs"):
                continue

            with open(base + ".meta") as mfile:
                meta = json.load(mfile)

            with open(base + ".refs") as rfile:
                refs = json.load(rfile)

            schema = meta.pop("schema")
            batch = meta.pop("batch")
            lang = (
                _determine_language(meta.get("batch", ""))
                or meta.get("partitions", {"values": ["en"]})["values"][0]
            )
            lab_lay = {}

            sqlc = SQLCorpus(meta, schema, batch, lang, lab_lay)

            for r in refs:
                sr = sqlc.attribute(r["entity"], r["layer"], r["attribute"])
                self.assertEqual(r["ref"], sr.ref)
                for tab, conds in r["joins"].items():
                    print("table", tab)
                    self.assertTrue(tab in sr.joins)
                    for cond in conds:
                        print("condition", cond)
                        try:
                            self.assertTrue(cond in sr.joins[tab])
                        except:
                            import pdb

                            pdb.set_trace()

    async def test_conversions(self):
        """
        Test that we can convert dqd to SQL
        """
        self.maxDiff = None
        test_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "test_data")
        names = {
            os.path.splitext(i)[0]
            for i in os.listdir(test_dir)
            if os.path.splitext(i)[0].isnumeric()
        }
        for n in sorted(names):

            base = os.path.join(test_dir, n)

            if any(
                not os.path.exists(base + ext)
                for ext in (".dqd", ".sql", ".msql", ".meta")
            ):
                continue

            with open(base + ".dqd") as dfile:
                dqd = dfile.read().strip() + "\n"

            with open(base + ".sql") as sfile:
                sql = sfile.read()
                sql = sqlparse.format(sql, reindent=True, keyword_case="upper").strip()
            with open(base + ".msql") as msfile:
                meta_q = msfile.read()
                meta_q = sqlparse.format(
                    meta_q, reindent=True, keyword_case="upper"
                ).strip()
            with open(base + ".meta") as mfile:
                meta = json.load(mfile)
            lg = _determine_language(meta["batch"]) or ""
            kwa = dict(
                schema=meta["schema"],
                batch=meta["batch"],
                config=meta,
                lang=lg,
            )
            json_query = dqd_to_json(dqd, meta)
            sql_query, meta_json, post_processes = json_to_sql(json_query, **kwa)
            self.assertTrue(meta_json is not None)
            self.assertTrue(post_processes is not None)
            self.assertEqual(sql_norm(sql_query), sql_norm(sql))
            mq, _ = get_segment_meta_script(
                meta,
                [lg],
                meta["batch"],
            )
            mm = sqlparse.format(mq, reindent=True, keyword_case="upper")
            self.assertEqual(sql_norm(meta_q), sql_norm(mm))
