import aiofiles
import json
import os
import psycopg2

from textwrap import dedent


class SQLstats:
    check_tbl = lambda x, y: dedent(
        f"""
        SELECT EXISTS (
               SELECT 1
                 FROM information_schema.tables
                WHERE table_schema = '{x}'
                  AND table_name = '{y}');"""
    )

    copy_tbl = lambda x, y, z: dedent(
        f"""
        COPY {x}.{y} {z}
        FROM STDIN
        WITH CSV QUOTE E'\b' DELIMITER E'\t';"""
    )

    main_corp = dedent(
        f"""
        INSERT
          INTO main.corpus (name, current_version, corpus_template, schema_path, token_counts)
        VALUES (%s, %s, %s, %s, %s);"""
    )

    token_count = lambda x, y: dedent(
        f"""
        SELECT count(*)
          FROM {x}.{y};"""
    )


class Table:
    def __init__(self, schema, name, columns=None):
        self.schema = schema
        self.name = name
        self.columns = columns

    def col_repr(self):
        return "(" + ", ".join(self.columns) + ")"


class Importer:
    def __init__(self, connection, template):
        self.connection = connection
        self.template = template
        self.name = self.template["meta"]["name"]
        self.version = self.template["meta"]["version"]
        self.schema = self.name + str(self.version)
        self.token_count = None

    async def create_constridx(self, constr_idxs):
        async with self.connection.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(constr_idxs)

    async def _check_tbl_exists(self, table):
        async with self.connection.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                script = SQLstats.check_tbl(table.schema, table.name)
                await cur.execute(script)
                res = await cur.fetchone()
                if res[0]:
                    return True
                else:
                    raise Exception(f"Error: table '{table.name}' does not exist.")

    async def _copy_tbl(self, data_f):
        async with aiofiles.open(data_f) as f:
            headers = await f.readline()
            headers = headers.split("\t")
            # await f.seek(0)

            data_f = os.path.basename(data_f)

            table = Table(self.schema, data_f.split(".")[0], headers)

            await self._check_tbl_exists(table)

            async with self.connection.connection() as conn:
                await conn.set_autocommit(True)
                async with conn.cursor() as cur:
                    cop = SQLstats.copy_tbl(table.schema, table.name, table.col_repr())
                    try:
                        async with cur.copy(cop) as copy:
                            while data := await f.read():
                                await copy.write(data)
                        return True
                    except Exception as e:
                        raise e

    async def import_corpus(self, data_dir):
        files = [
            os.path.join(data_dir, f)
            for f in os.listdir(data_dir)
            if f.endswith(".csv")
        ]

        for f in files:
            await self._copy_tbl(f)

        self.token_count = await self.get_token_count()

    async def get_token_count(self):
        """
        count inserted words/tokens in DB and return
        TODO: not working for parallel
        """

        token = self.template["firstClass"]["token"] + "0"

        async with self.connection.connection() as conn:
            async with conn.cursor() as cur:
                query = SQLstats.token_count(self.schema, token)
                await cur.execute(query)
                res = await cur.fetchone()
                if res:
                    count = res[0]
                else:
                    count = 5000
                    # raise Exception

        return {token: count}

    async def create_entry_maincorpus(self):
        async with self.connection.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    SQLstats.main_corp,
                    (
                        self.name,
                        self.version,
                        json.dumps(self.template),
                        self.schema,
                        json.dumps(self.token_count),
                    ),
                )