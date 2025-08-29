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
 , globals           jsonb
)
AS $$
   DECLARE
      k        text;
      val      jsonb;
      ak       text;
      avalue   jsonb;
      mk       text;
      mvalue   jsonb;
      subk     text;
      subvalue jsonb;
      gk       text;
      gval     jsonb;
      gak      text;
      gavalue  jsonb;
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
               -- Meta sub-attributes
               FOR mk, mvalue IN
                  SELECT * FROM jsonb_each(avalue)
               LOOP
                  IF jsonb_typeof(mvalue) = 'object' THEN
                     IF 'description' ? mvalue THEN
                        UPDATE main.corpus mc
                           SET
                              corpus_template = jsonb_set(
                                 corpus_template,
                                 format('{layer,%s,attributes,meta,%s,description}', k, mk)::text[],
                                 mvalue::jsonb->'description',
                                 TRUE
                              )
                           WHERE mc.corpus_id = $1;
                     END IF;
                     FOR subk, subvalue IN
                        SELECT * FROM jsonb_each(mvalue::jsonb->'keys')
                     LOOP
                        UPDATE main.corpus mc
                           SET
                              corpus_template = jsonb_set(
                                 corpus_template,
                                 format('{layer,%s,attributes,meta,%s,keys,%s,description}', k, mk, subk)::text[],
                                 subvalue::jsonb,
                                 TRUE
                              )
                           WHERE mc.corpus_id = $1;
                     END LOOP;
                  ELSE
                     UPDATE main.corpus mc
                        SET
                           corpus_template = jsonb_set(
                              corpus_template,
                              format('{layer,%s,attributes,meta,%s,description}', k, mk)::text[],
                              mvalue::jsonb,
                              TRUE
                           )
                        WHERE mc.corpus_id = $1;
                  END IF;
               END LOOP;
            ELSE
               -- Non-meta attribute
               IF jsonb_typeof(avalue) = 'object' THEN
                  IF avalue ? 'description' THEN
                     UPDATE main.corpus mc
                        SET
                           corpus_template = jsonb_set(
                              corpus_template,
                              format('{layer,%s,attributes,%s,description}', k, ak)::text[],
                              avalue::jsonb->'description',
                              TRUE
                           )
                        WHERE mc.corpus_id = $1;
                  END IF;
                  FOR subk, subvalue IN
                     SELECT * FROM jsonb_each(avalue::jsonb->'keys')
                  LOOP
                     UPDATE main.corpus mc
                        SET
                           corpus_template = jsonb_set(
                              corpus_template,
                              format('{layer,%s,attributes,%s,keys,%s,description}', k, ak, subk)::text[],
                              subvalue::jsonb,
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
            END IF;
         END LOOP;
      END LOOP;
      -- global attributes now
      FOR gk, gval IN
         SELECT * FROM jsonb_each(globals)
      LOOP
         FOR gak, gavalue IN
            SELECT * FROM jsonb_each(gval)
         LOOP
            UPDATE main.corpus mc
               SET
                  corpus_template = jsonb_set(
                     corpus_template,
                     format('{globalAttributes,%s,keys,%s,description}', gk, gak)::text[],
                     gavalue::jsonb,
                     TRUE
                  )
               WHERE mc.corpus_id = $1;
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


CREATE OR REPLACE PROCEDURE main.update_corpus(
   live_version      int
 , updating_version  int
)
AS $$
   DECLARE
      _initial_state    main.corpus_state;
      _history_entry    jsonb;
   BEGIN
      IF (
         SELECT NOT EXISTS (
                  SELECT 1
                    FROM main.corpus_history
                   WHERE target = live_version
                )
         )
      THEN
         SELECT created_at
              , current_version
              , corpus_template
              , description
              , mapping
              , name
              , sample_query
              , schema_path
              , token_counts
              , version_history
           INTO _initial_state
           FROM main.corpus
          WHERE corpus_id = live_version
              ;
      END IF;

      INSERT
        INTO main.corpus_history (target, source, initial_state)
      SELECT live_version
           , updating_version
           , _initial_state
   RETURNING jsonb_build_array(
                jsonb_build_array(target, source)
             )
        INTO _history_entry
           ;

      UPDATE main.corpus
         SET enabled = FALSE
       WHERE corpus_id = updating_version
           ;

        WITH upd AS (
            SELECT created_at
                 , current_version
                 , corpus_template
                 , description
                 , mapping
                 , name
                 , sample_query
                 , schema_path
                 , token_counts
              FROM main.corpus
             WHERE corpus_id = updating_version
             )
      UPDATE main.corpus
         SET created_at      = upd.created_at
           , current_version = upd.current_version
           , corpus_template = upd.corpus_template
           , description     = upd.description
           , mapping         = upd.mapping
           , name            = upd.name
           , sample_query    = upd.sample_query
           , schema_path     = upd.schema_path
           , token_counts    = upd.token_counts
           , version_history = coalesce(version_history, '[]'::jsonb) || _history_entry
        FROM upd
       WHERE corpus_id = live_version
           ;
   END
$$ LANGUAGE plpgsql SECURITY DEFINER;

ALTER PROCEDURE main.update_corpus
  SET search_path = pg_catalog,pg_temp;

REVOKE EXECUTE ON PROCEDURE main.update_corpus FROM public;
GRANT EXECUTE ON PROCEDURE main.update_corpus TO lcp_production_importer;

