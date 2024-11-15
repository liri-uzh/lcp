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
os.environ["_TEST"] = "true"

from lcpvian.app import create_app

# from lcpvian.sock import handle_redis_response
from lcpvian.utils import _meta_query


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

            kwa = dict(
                schema=meta["schema"],
                batch=meta["batch"],
                config=meta,
                lang=_determine_language(meta["batch"]),
            )
            json_query = dqd_to_json(dqd, meta)
            sql_query, meta_json, post_processes = json_to_sql(json_query, **kwa)
            self.assertTrue(meta_json is not None)
            self.assertTrue(post_processes is not None)
            self.assertEqual(sql_norm(sql_query), sql_norm(sql))
            cb: Batch = (meta["idx"], meta["schema"], meta["batch"], 1)
            mq = _meta_query(cb, meta)
            mm = sqlparse.format(mq, reindent=True, keyword_case="upper")
            self.assertEqual(sql_norm(meta_q), sql_norm(mm))
