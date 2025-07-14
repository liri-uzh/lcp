\c lcp_production lcp_production_owner

CREATE OR REPLACE PROCEDURE main.update_corpus_meta(
   corpus_id         int
 , metadata_json     jsonb
)
AS $$
   BEGIN

    UPDATE main.corpus mc
        SET
            corpus_template = jsonb_set(
               mc.corpus_template,
               '{meta}',
               mc.corpus_template->'meta' || $2
            )
        WHERE mc.corpus_id = $1;
   END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

ALTER PROCEDURE main.update_corpus_meta
  SET search_path = pg_catalog,pg_temp;

REVOKE EXECUTE ON PROCEDURE main.update_corpus_meta FROM public;
GRANT EXECUTE ON PROCEDURE main.update_corpus_meta TO lcp_production_importer;


CREATE OR REPLACE PROCEDURE main.update_corpus_descriptions(
   corpus_id         int
 , descriptions      jsonb
)
AS $$
   DECLARE
      k        text;
      val      jsonb;
      ak       text;
      avalue   jsonb;
      mk       text;
      mvalue   jsonb;
   BEGIN
      -- Loop over each key-value pair in the updates JSON object
      FOR k, val IN
         SELECT * FROM jsonb_each(descriptions)
      LOOP
         IF val ? 'description' THEN
            UPDATE main.corpus mc
               SET
                  corpus_template = jsonb_set(
                     corpus_template,
                     format('{layer,%s,description}', k)::text[],
                     val::jsonb->'description',
                     TRUE
                  )
               WHERE mc.corpus_id = $1;
         END IF;
         IF NOT val ? 'attributes' THEN
            CONTINUE;
         END IF;
         FOR ak, avalue IN
            SELECT * FROM jsonb_each(val->'attributes')
         LOOP
            IF ak = 'meta' AND jsonb_typeof(avalue) = 'object' THEN
               FOR mk, mvalue IN
                  SELECT * FROM jsonb_each(avalue)
               LOOP
                  UPDATE main.corpus mc
                     SET
                        corpus_template = jsonb_set(
                           corpus_template,
                           format('{layer,%s,attributes,meta,%s,description}', k, mk)::text[],
                           mvalue::jsonb,
                           TRUE
                        )
                     WHERE mc.corpus_id = $1;
               END LOOP;
            ELSE
               UPDATE main.corpus mc
                  SET
                     corpus_template = jsonb_set(
                        corpus_template,
                        format('{layer,%s,attributes,%s,description}', k, ak)::text[],
                        avalue::jsonb,
                        TRUE
                     )
                  WHERE mc.corpus_id = $1;
            END IF;
         END LOOP;
      END LOOP;
   END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

ALTER PROCEDURE main.update_corpus_descriptions
  SET search_path = pg_catalog,pg_temp;

REVOKE EXECUTE ON PROCEDURE main.update_corpus_descriptions FROM public;
GRANT EXECUTE ON PROCEDURE main.update_corpus_descriptions TO lcp_production_importer;


CREATE OR REPLACE PROCEDURE main.update_corpus_projects(
   corpus_id         int
 , pid               uuid
 , pids              text
)
AS $$
   BEGIN
      UPDATE main.corpus mc
         SET project_id = $2
         WHERE mc.corpus_id = $1;

      UPDATE main.corpus mc
         SET corpus_template = jsonb_set(mc.corpus_template, '{project}', ('"' || $2::text || '"')::jsonb)
         WHERE mc.corpus_id = $1;

      UPDATE main.corpus mc
         SET corpus_template = jsonb_set(mc.corpus_template, '{projects}', $3::jsonb)
         WHERE mc.corpus_id = $1;
   END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

ALTER PROCEDURE main.update_corpus_projects
  SET search_path = pg_catalog,pg_temp;

REVOKE EXECUTE ON PROCEDURE main.update_corpus_projects FROM public;
GRANT EXECUTE ON PROCEDURE main.update_corpus_projects TO lcp_production_importer;
